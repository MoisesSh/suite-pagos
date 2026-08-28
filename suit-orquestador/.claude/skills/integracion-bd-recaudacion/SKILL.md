---
name: integracion-bd-recaudacion
description: Integración de solo lectura con la base de datos externa RECAUDACION (CONATEL) — router, modelos espejo managed=False, SQL crudo, degradación a 503 cuando no está disponible, y el servicio de habilitación de operadores.
---

# Integración con BD externa RECAUDACION

Skill para trabajar con la única integración de datos externa real del backend: una segunda conexión Postgres de **solo lectura** a la base de datos "RECAUDACION" de CONATEL (un sistema ajeno, fuera del control de este proyecto). Es el caso de uso que justifica que `operador` sea la única app feature con capas `application/`/`infraestructure/` realmente pobladas (ver [[arquitectura-onion-feature-scream]]).

---

## Regla número uno: esta base es opcional y ajena

Todo el diseño gira en torno a una premisa: **si `RECAUDACION_DATABASE_URL` no está configurada, el resto del sistema debe seguir funcionando con normalidad**, y las funciones que dependen de ella deben degradar a `503`, no tumbar la app. No rompas esta garantía al tocar este código.

---

## Configuración de conexión (`FitVen/settings.py`)

```python
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
}

RECAUDACION_DATABASE_URL = env('RECAUDACION_DATABASE_URL', default='')
RECAUDACION_ALIAS = 'recaudacion'

if RECAUDACION_DATABASE_URL:
    DATABASES[RECAUDACION_ALIAS] = env.db_url_config(RECAUDACION_DATABASE_URL)
    DATABASES[RECAUDACION_ALIAS]['CONN_MAX_AGE'] = 0   # sin conexiones persistentes: base ajena
    DATABASES[RECAUDACION_ALIAS].setdefault('OPTIONS', {})
    DATABASES[RECAUDACION_ALIAS]['OPTIONS']['connect_timeout'] = 5

DATABASE_ROUTERS = ['FitVen.routers.RecaudacionRouter']
```

Si la variable de entorno está vacía, el alias `'recaudacion'` **directamente no existe** en `DATABASES` — esa ausencia es la señal que usa `HabilitacionService.disponible()`, no un try/except de conexión fallida en el arranque.

`.env.example` documenta el rol Postgres requerido: usuario `fitelven_ro` con permisos únicamente `CONNECT` + `USAGE` + `SELECT` sobre 4 tablas específicas. **Nunca pidas más permisos que esos** para esta conexión — el diseño depende de que el rol SQL, no solo el código Django, imponga la restricción de solo lectura.

---

## Router — `FitVen/routers.py` (completo)

```python
class RecaudacionRouter:
    MODULO_ESPEJO = 'apps.operador.infraestructure.recaudacion_models'

    def _es_de_recaudacion(self, model) -> bool:
        return model.__module__ == self.MODULO_ESPEJO

    def db_for_read(self, model, **hints):
        if self._es_de_recaudacion(model):
            return settings.RECAUDACION_ALIAS
        return None

    def db_for_write(self, model, **hints):
        # Devuelve el alias igual: es el rol de solo lectura de Postgres quien
        # rechaza la escritura, no el router.
        if self._es_de_recaudacion(model):
            return settings.RECAUDACION_ALIAS
        return None

    def allow_relation(self, obj1, obj2, **hints):
        uno = self._es_de_recaudacion(type(obj1))
        dos = self._es_de_recaudacion(type(obj2))
        if uno or dos:
            return uno and dos
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == settings.RECAUDACION_ALIAS:
            return False
        model = hints.get('model')
        if model is not None and self._es_de_recaudacion(model):
            return False
        return None
```

**Identificación por módulo de origen del modelo, no por `app_label` ni `Meta.managed`.** Cualquier clase Python definida dentro de `apps/operador/infraestructure/recaudacion_models.py` queda automáticamente enrutada a la conexión externa — no necesitas registrarla en ninguna lista aparte. Si en el futuro se necesita reflejar otra tabla de RECAUDACION, **agrégala en ese mismo archivo**, no crees un módulo espejo nuevo (el router no lo reconocería).

`allow_migrate` siempre devuelve `False` para esta conexión: **nunca correrás `migrate` contra RECAUDACION**, ni intencionalmente ni por accidente.

---

## Modelos espejo (`apps/operador/infraestructure/recaudacion_models.py`)

Todos con `managed = False`. Solo se declaran las columnas que el servicio realmente usa — las tablas reales tienen muchas más (hasta ~38 columnas).

| Modelo | `db_table` | PK | Campos declarados | Nota |
|---|---|---|---|---|
| `UsuarioRecaudacionWeb` | `usuariorecaudacionweb` | `idusuario` | `nombre` | `nombre == 'ILEGAL'` es un centinela de operador ilegal — se excluye explícitamente en la consulta |
| `OperadorRecaudacion` | `operadorrecaudacion` | `idoperador` | `idusuario`, `rif`, `nombre` | |
| `Habilitacion` | `habilitacion` | `idhabilitacion` | `idoperador`, `idtempoperador`, `tienehabilitacion`, `nrohabilitacion`, `observacion` | `fecha_vencimiento` existe en la tabla real pero está NULL en el 100% de las filas conocidas — deliberadamente **no** se declara |
| `RegistroTempOperador` | `registrotempoperador` | `idregistrotempoperador` | `idusuario`, `idhabilitacion`, `rif`, `nombre`, `nombrecomercial`, `numerohabilitacion`, `fecharegistro` | Tabla raíz de la consulta; un mismo RIF puede tener varios registros (hay casos con 42+ duplicados) |

**No se usa el ORM para el JOIN entre estas 4 tablas** — un JOIN entre bases de datos distintas es imposible en Django/SQL. Se usa SQL crudo vía `connections[alias].cursor()`.

**Al añadir un campo nuevo a uno de estos modelos**: agrégalo solo si el servicio lo va a usar. No repliques el esquema completo de la tabla real "por si acaso" — el patrón deliberado es un espejo mínimo.

---

## El servicio: `HabilitacionService` (`apps/operador/application/habilitacion.py`)

`staticmethod`s, sin estado propio:

```python
class HabilitacionService:
    @staticmethod
    def disponible() -> bool:
        return settings.RECAUDACION_ALIAS in settings.DATABASES

    @staticmethod
    def consultar(rif: str) -> ResultadoHabilitacion:
        if not HabilitacionService.disponible():
            raise RecaudacionNoDisponible('La base de datos de RECAUDACION no está configurada.')
        rif_norm = rif_canonico(rif)
        try:
            with connections[settings.RECAUDACION_ALIAS].cursor() as cursor:
                cursor.execute(_SQL_POR_RIF, [rif_norm])
                fila = cursor.fetchone()
        except DatabaseError as exc:
            raise RecaudacionNoDisponible(f'No se pudo consultar RECAUDACION: {exc}') from exc
        return _clasificar(fila)

    @staticmethod
    def sincronizar(usuario) -> ResultadoHabilitacion:
        resultado = HabilitacionService.consultar(usuario.rif)
        DatosOperador.objects.filter(usuario=usuario).update(
            estado_habilitacion=resultado.estado,
            consultado_at=timezone.now(),
        )
        return resultado
```

- `_SQL_POR_RIF` hace un `LEFT JOIN` de las 4 tablas, filtrando `usuariorecaudacionweb.nombre <> 'ILEGAL'`.
- `clasificar()` usa una regex sobre `nrohabilitacion`: contiene "TRAMITE" → `EN_TRAMITE`; sin dígitos → `NO_HABILITADO`; con dígitos → `HABILITADO`. **El número manda sobre el flag `tienehabilitacion`** cuando hay inconsistencia entre ambos — es una directriz de negocio explícita, no un descuido.
- `sincronizar()` persiste **solo** `estado_habilitacion` + `consultado_at` en `DatosOperador` (la BD propia). El resto de los datos de habilitación **no se copian** — viven en RECAUDACION y se consultan on-demand (la consulta toma ~2.4ms; copiar todo generaría desincronización sin necesidad).

**Diseño explícito y deliberado**: este servicio **nunca aprueba ni rechaza** una habilitación — solo informa el estado que ve en RECAUDACION. La decisión regulatoria la toma siempre un funcionario humano de CONATEL vía `RevisionHabilitacionView`. No cambies este servicio para que tome decisiones automáticas sin que el usuario lo pida explícitamente — es una decisión de producto, no un descuido técnico.

---

## Dónde se consume

| Vista | App | Rol |
|---|---|---|
| `MiHabilitacionView` | `operador` | El propio operador consulta su estado (`sincronizar()`) |
| `ConsultarHabilitacionView` | `conatel` | Un funcionario consulta cualquier RIF (`consultar()`) |
| `RevisionHabilitacionView` | `conatel` | Cola de revisión: sincroniza **todos** los operadores en un solo GET — documentado como "GET que escribe", sin paginar, aceptable solo a la escala actual (decenas de operadores). **Si el volumen crece, esto necesita rediseño** (paginación + escritura async), no es un patrón a replicar en un endpoint nuevo. |

---

## Manejo de errores → 503

`RecaudacionNoDisponible(Exception)` se lanza en dos puntos: si `disponible()` es `False`, o si `connections[alias].cursor()` lanza `DatabaseError` (conexión caída, timeout de 5s agotado, etc.). Las 3 vistas repiten el mismo patrón — replícalo si añades una cuarta:

```python
try:
    resultado = HabilitacionService.consultar(rif)   # o .sincronizar(usuario)
except RecaudacionNoDisponible as exc:
    return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
```

El resto de la aplicación (auth, otros perfiles, geografía, etc.) **no depende de esta conexión** y sigue operando con normalidad si RECAUDACION cae.

---

## RIF: formatos incompatibles entre sistemas

FITELVEN y RECAUDACION almacenan el RIF en formatos distintos. Toda comparación pasa por las funciones puras de `apps/shared/domain/rif.py`:

```python
rif_canonico(rif)      # normaliza para comparar/consultar
rif_presentable(rif)   # formatea para mostrar al usuario
```

**Nunca compares o consultes un RIF sin pasar por `rif_canonico()` primero** — es la causa más probable de un falso "no encontrado" al integrar con RECAUDACION.

---

## Archivo SQL de referencia (`sql/habilitacion_recaudacion.sql`)

Documenta la consulta SQL original (equivalente a una query legacy de un sistema Yii2 previo) con el mapeo de nombres de tabla reales vs. los placeholders del boceto inicial. **Es documentación de referencia, no se ejecuta desde la app** — si modificas `_SQL_POR_RIF` en el servicio, actualiza este archivo en paralelo para que no quede desactualizado.

Hay también `sql/geo_desde_censo.sh`, una integración **distinta y no relacionada** (importa división político-territorial desde otra base ajena, `CENSO_PRODUCCION`, vía `COPY`, en una ejecución única post-migración). Es un patrón hermano si en el futuro se generaliza "integraciones con bases externas de otros sistemas", pero no comparte código con RECAUDACION.

---

## Tests

Los tests de `apps/operador/tests.py` **nunca tocan la BD real** — mockean `HabilitacionService.consultar`/`.sincronizar`. Ver el patrón exacto en [[testing-backend-django]], incluyendo el test explícito `test_recaudacion_caida_devuelve_503`.

---

## Comandos

### 1. Añadir un campo/tabla nueva desde RECAUDACION

```
@skill agrega el campo/tabla [x] desde RECAUDACION
```

1. Agrega el modelo o campo en `apps/operador/infraestructure/recaudacion_models.py` con `managed = False`, solo las columnas que realmente vas a usar.
2. Si es una tabla nueva, confirma que el rol SQL `fitelven_ro` tenga `SELECT` sobre ella — pídelo explícitamente, no asumas que ya lo tiene.
3. Si necesitas un JOIN nuevo, hazlo con SQL crudo vía `connections[settings.RECAUDACION_ALIAS].cursor()`, no intentes un JOIN ORM entre bases.
4. Actualiza `sql/habilitacion_recaudacion.sql` (o crea un archivo de referencia análogo) documentando la query.
5. Envuelve cualquier consulta nueva en el mismo patrón try/except → `RecaudacionNoDisponible` → 503.
6. Mockea el punto de entrada en los tests nuevos, nunca la conexión real.

### 2. Diagnosticar un 503 de habilitación

```
@skill por qué falla la consulta de habilitación
```

Verifica en orden: ¿`RECAUDACION_DATABASE_URL` está seteada en el entorno? ¿el rol `fitelven_ro` sigue teniendo `SELECT` sobre las 4 tablas? ¿el RIF se está normalizando con `rif_canonico()` antes de consultar? ¿el timeout de 5s es suficiente para la latencia actual de red hacia esa base?
