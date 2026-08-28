---
name: supervision-modelos-bd
description: Reglas y guía de auditoría para el modelado de bases de datos en Django y PostgreSQL dentro de una arquitectura Onion — normalización, integridad referencial (on_delete), relaciones (FK vs M2M vs 1:1), índices, claves primarias UUID, migraciones seguras, rendimiento, prevención de problemas comunes, monitoreo y seguridad de datos personales, con checklist de supervisión y ejemplos genéricos.
---

# Supervisión y Auditoría de Modelos de Base de Datos (Backend)

Skill para auditar, supervisar y crear modelos en la capa de dominio de un backend Django sobre PostgreSQL organizado con arquitectura Onion. Garantiza consistencia arquitectónica, integridad referencial estricta, alta eficiencia en consultas y migraciones seguras sin tiempo de inactividad.

---

## 1. Contexto Arquitectónico y Fuente de la Verdad

1. **Kernel de dominio compartido:**
   Todos los modelos ORM persistentes del sistema deben residir centralizados en un único módulo de dominio (p. ej. `domain/models.py` de una app "shared"/"core"). Las apps de feature (organizadas por dominio de negocio, no por capa técnica) son capas de API/Servicio que consumen ese dominio; no deben declarar modelos propios salvo modelos espejo no gestionados (`managed=False`) para integraciones externas.
2. **Independencia del Dominio (Onion):**
   Los modelos representan entidades puras del negocio. No deben importar ni depender de serializers de la capa de API, vistas, esquemas de frontend ni librerías de presentación.
3. **Realidad multi-base (cuando aplica):**
   - Una base propia de lectura/escritura para el dominio del proyecto.
   - Bases externas de solo lectura de sistemas de terceros, enrutadas vía un `Router` de base de datos dedicado, con modelos `managed=False`.
   - **Catálogos de referencia importados:** cuando una tabla (p. ej. una división territorial) es una réplica local de una fuente externa, usa como clave primaria el identificador original de esa fuente (a menudo entero), a diferencia del resto del dominio.

---

## 2. Clave Primaria y Modelo Base (`BaseModel`)

### Regla General: UUID ordenable en el tiempo (UUIDv7)
Toda entidad del dominio propia del proyecto debe heredar de `BaseModel`:

```python
class BaseModel(models.Model):
    """Modelo abstracto base con UUIDv7 y timestamps."""
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

- **Por qué UUIDv7:** A diferencia de UUIDv4 (aleatorio), UUIDv7 incluye un prefijo temporal que preserva la localidad secuencial en los índices B-Tree de PostgreSQL, evitando la fragmentación de páginas y la degradación de rendimiento en inserciones.
- **Excepción documentada:** Los catálogos de referencia importados desde un sistema externo (p. ej. divisiones territoriales) heredan directamente de `models.Model` con PK entera para mantener paridad exacta con la fuente.

---

## 3. Normalización vs. Catálogos vs. Enums

### Cuándo usar `models.TextChoices` (Enums en código)
Úsalo cuando los valores posibles son finitos, cerrados y gobiernan flujos de lógica/permisos en el código:
- `Pedido.Estatus` (`creado`, `en_proceso`, `completado`, `cancelado`)
- `Cliente.Prioridad` (`alta`, `media`, `baja`)

### Cuándo usar Modelos de Catálogo (Tablas maestras)
Úsalo cuando el catálogo es administrable, extensible sin despliegue de código, o posee atributos descriptivos/metadatos:
- `CategoriaProducto` (código, nombre, icono)
- `TipoDocumento` (nombre, formato)
- `Region`, `Estado`, `Municipio` (catálogo territorial)

### Regla Antipatrón: Cero texto libre para conceptos relacionales
- **Patrón de error típico:** un campo como `region_texto` o `categoria_texto` definido como `CharField` de texto libre, donde acaban acumulándose variantes sucias de la misma idea (`'Norte'`, `'norte'`, `'NTE'`). La corrección es migrarlo a una FK (`Region`) o a un M2M contra un catálogo real.
- **Caso derivado — el mismo concepto duplicado en dos campos distintos:** una entidad tiene un campo de texto libre (ej. `tipo`) cuyos valores válidos coinciden, en la práctica, con los códigos de un catálogo con el que esa misma entidad **ya tiene** una relación — típicamente una M2M pensada originalmente para otro propósito (ej. `tecnologias`). El resultado son dos representaciones paralelas del mismo dato — una como texto suelto, otra como referencia real a catálogo — que pueden desincronizarse entre sí sin que nada lo impida, porque nada obliga a que el texto libre coincida con lo seleccionado en la relación. **Antes de agregar (o de dejar como está) un campo de texto libre, revisa si la entidad ya tiene una FK o M2M a un catálogo cuyos valores cubran ese mismo concepto.** Si es así, unifica en una sola representación — la del catálogo — en vez de mantener las dos; el campo de texto libre debe eliminarse o derivarse de la relación existente (ej. una property o un `SerializerMethodField` que lea el primer elemento de la M2M), nunca coexistir con ella como una fuente de verdad separada.
- **Criterio de supervisión:** si un campo almacena un concepto que pertenece a una lista de opciones o a una entidad territorial/técnica, **nunca** uses `CharField` abierto. Debe ser una FK a un catálogo o un `TextChoices` — y si ese catálogo ya es alcanzable desde otra relación de la misma entidad, no crees un segundo campo para el mismo concepto.

### Desnormalización Justificada
Solo se admite desnormalizar si cumple tres condiciones:
1. Resuelve una barrera técnica crítica (ej. consultas entre bases distintas o agregaciones masivas en dashboards).
2. Es mantenido de forma 100% automática por servicios o señales, jamás editable a mano.
3. Está explícitamente documentado en el modelo.

*Ejemplo genérico:* un booleano local en `Cliente` derivado de un veredicto calculado por un sistema externo, mantenido automáticamente por un servicio de sincronización, para permitir filtros SQL directos (`Q()`) en KPIs de un dashboard sin tener que cruzar conexiones a la base externa en cada consulta.

---

## 4. Tipos de Relaciones e Integridad Referencial (`on_delete`)

### Matriz de Decisión de Relaciones

| Caso | Tipo de Campo | Ejemplo Genérico | Regla de Oro |
|---|---|---|---|
| Perfil dependiente exclusivo de una entidad principal | `OneToOneField` | `DatosFacturacion` de un `Cliente` | `on_delete=models.CASCADE`, `related_name` en singular. |
| Entidad secundaria perteneciente a un padre | `ForeignKey` | `LineaPedido.pedido`, `Representante.cliente` | `on_delete=models.CASCADE`, `related_name` en plural. |
| Referencia a catálogo o entidad maestra | `ForeignKey` | `Pedido.region` → `Region`, `Producto.categoria` → `CategoriaProducto` | **Siempre `on_delete=models.PROTECT`**. Nunca borres un catálogo en cascada. |
| Auditoría / quién ejecutó una acción | `ForeignKey` | `Pedido.aprobado_por`, `Verificacion.verificado_por` | `on_delete=models.SET_NULL`, `null=True, blank=True`. |
| Asociación N:M simple | `ManyToManyField` | `Producto.etiquetas` → `Etiqueta` | Usar cuando la relación no requiere almacenar atributos adicionales. |
| Asociación N:M con metadatos o ciclo de vida | Modelo intermedio explícito | `ClienteServicio` (cliente, servicio, fecha_alta) | Definir `unique_together` o `UniqueConstraint` en la tabla puente. |

### Reglas estrictas de `related_name`
1. **Obligatorio:** Todo campo `ForeignKey`, `OneToOneField` y `ManyToManyField` debe declarar un `related_name` explícito.
2. **Plural para colecciones:** `related_name='pedidos'`, `related_name='productos'`, `related_name='clientes'`.
3. **Singular para 1:1:** `related_name='datos_facturacion'`, `related_name='evaluacion'`.
4. **Sentido semántico inverso:** Si `ClienteServicio.servicio` apunta a `Servicio`, su `related_name` debe ser `'clientes_interesados'`, no `'servicios'`.

---

## 5. Indexación y Restricciones en PostgreSQL

### Índices B-Tree Estratégicos
PostgreSQL indexa automáticamente las PKs y los campos con `unique=True`. Para el resto:
- **`db_index=True`:** Aplícalo en campos de alta cardinalidad o filtrado constante:
  - `Pedido.estatus` (filtro frecuente en listados y agregaciones de dashboard).
  - `Municipio.codigo`, `Parroquia.codigo`.
- **Índices compuestos (`Meta.indexes`):** Requeridos cuando las consultas filtran u ordenan concurrentemente por múltiples columnas:
  ```python
  class Meta:
      indexes = [
          # Optimiza filtros combinados usados por endpoints de listado público y dashboards internos:
          models.Index(fields=['estatus', 'tipo', 'region']),
      ]
  ```

### Restricciones de Unicidad (`UniqueConstraint` / `unique_together`)
Evita duplicidad lógica a nivel de motor SQL:
```python
# Ejemplo: un cliente no puede solicitar dos veces el mismo servicio al mismo proveedor
unique_together = ['cliente', 'proveedor', 'servicio']

# Ejemplo: un solo registro de verificación por cliente y ente verificador
unique_together = ['cliente', 'ente_verificador']
```

### Tipos de Datos y Validadores
- Usa `PositiveSmallIntegerField` para porcentajes (0-100) o puntajes pequeños, acompañado de `MaxValueValidator(100)`:
  ```python
  progreso = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
  ```
- Usa `DecimalField(max_digits=15, decimal_places=2)` para montos monetarios (`Pedido.monto_total`), jamás `FloatField`.
- Usa `EmailField` para correos electrónicos con `unique=True`.

---

## 6. Convenciones de Migraciones Seguras

Al modificar modelos existentes en producción:

1. **Separar Migración de Esquema y Migración de Datos:**
   Nunca mezcles en un solo archivo un `AddField` o `AlterField` con una mutación masiva de datos en Python.
   - Migración 1: Agregar campo nuevo (`null=True`).
   - Migración 2: Script `RunPython` para poblar o transformar los datos existentes.
   - Migración 3: Ajustar restricciones (`null=False`, `unique=True`, etc.) y eliminar campos obsoletos.
2. **Idempotencia y Reversibilidad:**
   Toda función `RunPython(forward_func, reverse_func)` debe tener:
   - Capacidad de ejecutarse múltiples veces sin fallar (idempotente).
   - Función reversa explícita (`reverse_func`) para permitir `migrate app [prev_migration]`.
3. **Uso exclusivo de `apps.get_model`:**
   En las migraciones, **nunca** importes modelos directamente (`from apps.dominio.models import Pedido`). Usa siempre `Pedido = apps.get_model('dominio', 'Pedido')` para respetar el estado histórico del esquema en ese punto de la historia.
4. **Preservación de Datos Históricos:**
   Si una columna se va a eliminar o reestructurar y contiene datos heredados dudosos, respalda el contenido en una tabla de auditoría/historial antes de eliminarla.

---

## 7. Antes de Agregar Campos Nuevos: Preguntar, No Inferir

Si una tarea implica agregar un campo nuevo a un modelo existente (o crear un modelo nuevo) y **no** especifica exactamente qué campo(s), de qué tipo, y para qué caso de uso concreto, el agente **debe preguntar explícitamente** al usuario o al coordinador antes de escribir el modelo o la migración. No inventes ni infieras el nombre, tipo o propósito del campo a partir de suposiciones sobre "lo que probablemente se necesita" — un campo mal diseñado desde el inicio (tipo incorrecto, catálogo vs texto libre, relación mal elegida) genera deuda técnica y migraciones correctivas después.

Preguntar específicamente:
- Qué campo(s) exactos hacen falta y su propósito/caso de uso real.
- Si el valor es de un conjunto cerrado (candidato a `TextChoices`) o abierto/administrable (candidato a catálogo con FK).
- Si puede repetirse (M2M) o es único por entidad (FK/campo simple).
- Si hay datos existentes que migrar/retrocompletar.

Solo después de tener esa respuesta, aplicar las reglas de las secciones 2-6 de esta skill para decidir el tipo de campo, la relación y la migración correctas.

---

## 8. Checklist de Auditoría para Nuevos Modelos o Cambios

Antes de aprobar un nuevo modelo o modificación en la capa de dominio, verifica:

- [ ] **Herencia:** ¿Hereda de `BaseModel` (UUID ordenable + timestamps) salvo que sea una tabla de catálogo importada?
- [ ] **Normalización:** ¿Hay campos `CharField` libres guardando datos que deberían ser FK a catálogo o `TextChoices`?
- [ ] **Integridad referencial:** ¿Todas las FK a catálogos tienen `on_delete=models.PROTECT`?
- [ ] **Cascadas:** ¿Las FK con `CASCADE` están limitadas estrictamente a hijos dependientes del ciclo de vida del padre?
- [ ] **Nombres inversos:** ¿Cada relación define un `related_name` explícito, correcto en número (singular/plural) y semántica?
- [ ] **Índices:** ¿Los campos filtrados por las vistas o servicios que consultan estos datos tienen `db_index=True` o están cubiertos por un `models.Index` compuesto?
- [ ] **Restricciones:** ¿Las relaciones compuestas tienen `unique_together` o `UniqueConstraint` para prevenir duplicados lógicos?
- [ ] **Representación:** ¿El modelo implementa `__str__` claro y seguro contra valores `None` (usando operador ternario si un FK es nullable)?
- [ ] **Metadatos:** ¿Declara `verbose_name` y `verbose_name_plural`?
- [ ] **Migraciones:** ¿Los cambios de esquema incluyen migración de datos reversible y sin bloqueos de tabla?

---

## 9. Rendimiento: N+1, `EXPLAIN ANALYZE`, Vacuum y Pooling

### N+1 — patrón de fuga típico y cómo detectarlo con confianza

Es común centralizar `select_related`/`prefetch_related` en un servicio compartido para que varias vistas de listado lo reutilicen:

```python
class PedidoService:
    _SELECT_RELATED = ('cliente', 'cliente__perfil', 'categoria', 'categoria__grupo')

    @staticmethod
    def activos():
        return Pedido.objects.filter(
            estatus__in=[Pedido.Estatus.APROBADO, Pedido.Estatus.ACTIVO],
        ).select_related(*PedidoService._SELECT_RELATED)
```

```python
# Vista de listado
Pedido.objects.select_related('region').prefetch_related('etiquetas').order_by('-created_at')
```

**Patrón de fuga real y recurrente:** cuando un serializer de *lista* evoluciona y se le agrega un campo `many=True` nuevo (un M2M, o un `SerializerMethodField` que recorre una relación), es común que el `prefetch_related`/`select_related` de la vista que alimenta ese serializer quede desactualizado — el propio autor del cambio se lo salta con frecuencia, porque el olvido está en el lado de la vista/servicio, no en el del serializer que se está editando. Y no es raro que el primer intento de arreglo tampoco sea completo: puede haber más de un campo relacionado nuevo (uno vía M2M explícito, otro vía una FK que el serializer empezó a leer con `source='fk.campo'`), y cada uno dispara su propio N+1 independiente.

**Regla de supervisión:** cada vez que un serializer de lista agregue un campo `many=True` o un `source` que atraviese una FK, la vista que lo alimenta debe revisar su `prefetch_related`/`select_related` en el mismo cambio — no después. La única forma confiable de verificarlo no es la revisión manual del código, sino un test de regresión que compare el número de queries ejecutadas al listar N objetos vs. M objetos (`django.test.utils.CaptureQueriesContext`): si el conteo crece con el número de objetos, hay un N+1, sin importar cuántas veces se haya revisado el `select_related` a simple vista. Reserva los serializers con relaciones anidadas pesadas (múltiples relaciones vía `SerializerMethodField`) para vistas de **detalle** (un solo objeto), donde ese costo no aplica de la misma forma; usa un serializer plano para listados.

### `EXPLAIN ANALYZE` — cómo verificar antes de optimizar

Nunca optimices a ciegas. Antes de agregar un índice o un `select_related`, mide:

```python
# Desde `manage.py shell` o un test temporal:
from django.db import connection
print(Pedido.objects.filter(estatus='pendiente').query)  # ver el SQL generado

with connection.cursor() as cursor:
    cursor.execute(f"EXPLAIN ANALYZE {Pedido.objects.filter(estatus='pendiente').query}")
    for fila in cursor.fetchall():
        print(fila[0])
```

Busca en la salida: `Seq Scan` sobre una tabla grande (candidato a índice), `Nested Loop` con alto `actual rows` por iteración (candidato a un `JOIN` mejor indexado o a desnormalizar), y la diferencia entre `cost` estimado y `actual time` (estadísticas desactualizadas → correr `ANALYZE nombre_tabla;`).

Un índice compuesto como el documentado en la §5 (`models.Index(fields=['estatus', 'tipo', 'region'])`) existe exactamente para que los filtros combinados de un endpoint de listado (por varios campos a la vez) no caigan en `Seq Scan` a medida que la tabla crece.

### Vacuum y Autovacuum

PostgreSQL no borra físicamente una fila al hacer `DELETE`/`UPDATE`; la marca como muerta (`dead tuple`) y `autovacuum` la recicla después. Relevante siempre que exista una tarea periódica de limpieza que hace `DELETE` en cascada sobre una entidad principal y todo lo que cuelga de ella (registros huérfanos no verificados, sesiones expiradas, etc.):

- Si esa tarea llega a borrar volúmenes grandes de una sola vez, vigila `n_dead_tup` en las tablas afectadas — un DELETE masivo periódico es exactamente el patrón que satura autovacuum si sus umbrales (`autovacuum_vacuum_scale_factor`) se dejan en el default.
- Verificación rápida: `SELECT relname, n_dead_tup, last_autovacuum FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY n_dead_tup DESC;` — si `last_autovacuum` está muy atrás y `n_dead_tup` crece, es momento de bajar el `scale_factor` para esas tablas específicas, no para toda la base.

### Connection Pooling

```python
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
}
...
# Conexión a un sistema externo: deliberadamente sin conexiones persistentes,
# porque la base es ajena y no vale la pena retener recursos sobre ella.
DATABASES['sistema_externo']['CONN_MAX_AGE'] = 0
```

**Punto de supervisión:** si la conexión `default` no define `CONN_MAX_AGE` explícito, hereda el default de Django (`0`, sin conexiones persistentes: una conexión TCP nueva por request). Con varios workers de aplicación concurrentes más un worker de tareas en segundo plano, eso puede significar varias conexiones abriéndose y cerrándose por segundo bajo carga. Es aceptable a baja escala, pero si el tráfico crece, las dos rutas estándar son:
1. **`CONN_MAX_AGE=60`** (o similar) en `default` — conexiones persistentes reutilizadas entre requests del mismo worker. Barato, sin infraestructura nueva.
2. **PgBouncer en modo `transaction`** — necesario si el número de workers/procesos supera lo que Postgres tolera en `max_connections`. Con este modo, Django **debe** desactivar cursores del lado del servidor (`DISABLE_SERVER_SIDE_CURSORS = True`), porque un cursor abierto en una transacción puede reasignarse a otra conexión física antes de cerrarse. Si se introduce SQL crudo con *prepared statements* explícitos, verifica primero la versión de PgBouncer: el soporte de prepared statements en modo transacción es relativamente reciente y depende del protocolo usado por el driver — no asumas que funciona sin probarlo.

El mismo razonamiento de la conexión a un sistema externo (`CONN_MAX_AGE=0`, timeout de conexión corto, no retener recursos de algo que no controlas) aplica a cualquier integración externa futura.

### Particionamiento

Un catálogo de referencia importado (de decenas/miles de filas fijas) nunca justifica partición. El candidato natural a particionar cuando un proyecto crece es una tabla de auditoría de solo-inserción (un historial de cambios de estatus, por ejemplo) que nunca se actualiza ni se borra por diseño — el patrón clásico de partición por rango de fecha (`created_at`) con `pg_partman` o particiones manuales mensuales, para poder archivar/eliminar particiones viejas sin un `DELETE` masivo (que generaría el mismo problema de `dead tuples` de la sección de Vacuum). No implementar antes de que la tabla muestre señales reales de tamaño (cientos de miles de filas o más) — particionar prematuramente es complejidad sin beneficio medible.

---

## 10. Prevención de Problemas Comunes

### Race conditions: retry-on-conflict vs. lock explícito

Un generador de códigos secuenciales legibles (número de pedido, código de seguimiento) que lee el último valor y calcula `siguiente = ultimo + 1` **sin bloquear la fila** es un `read-then-write` clásico:

```python
class GeneradorCodigoService:
    @staticmethod
    def generar(prefijo):
        """
        Nota: dos transacciones concurrentes pueden obtener el mismo
        secuencial; quien llama debe reintentar ante IntegrityError.
        """
        ...
```

Quien lo llama absorbe la colisión con reintento optimista, no con un lock:

```python
for _ in range(MAX_REINTENTOS):
    codigo = GeneradorCodigoService.generar(prefijo)
    try:
        with transaction.atomic():
            entidad = Modelo.objects.create(..., codigo=codigo)
        return entidad
    except IntegrityError:
        if Modelo.objects.filter(codigo=codigo).exists():
            continue  # colisión esperada: reintentar con el siguiente secuencial
        raise  # cualquier otro IntegrityError (unicidad de otro campo, etc.) se propaga
```

**Cuándo usar retry-on-conflict y cuándo `select_for_update()`:** el retry es preferible cuando las colisiones son raras y bloquear la fila "última con ese prefijo" serializaría *todos* los registros del mismo grupo — un cuello de botella peor que la colisión ocasional que resuelve. Usa `select_for_update()` en cambio cuando la operación es de alta frecuencia y el costo de un reintento es alto (por ejemplo, si el registro completo — no solo el número — fuera costoso de recrear), o cuando hay más de una fila que debe leerse y modificarse de forma consistente (ej. transferir un saldo entre dos cuentas).

Plantilla de `select_for_update()` para cuando sí haga falta:

```python
with transaction.atomic():
    ultimo = (
        Modelo.objects
        .select_for_update()
        .filter(codigo__startswith=patron)
        .order_by('-codigo')
        .first()
    )
    # ahora ninguna otra transacción puede leer esa fila hasta que esta termine
```

### Deadlocks

El riesgo aparece cuando dos servicios distintos toman locks sobre las mismas dos tablas en **orden inverso** (`A` luego `B` en un flujo, `B` luego `A` en otro) bajo `select_for_update`. **Regla de supervisión:** si se introduce `select_for_update()`, documentar y mantener un orden de adquisición de locks consistente entre todos los servicios que toquen las mismas tablas.

### Fugas de conexión

Django cierra la conexión al final de cada request/task automáticamente (con `CONN_MAX_AGE=0`, después de cada uno; con `CONN_MAX_AGE>0`, cuando expira). El punto de riesgo típico es un servicio que abre una conexión manual fuera de ese ciclo — por ejemplo, uno que hace consultas directas contra una base externa vía `connections[alias].cursor()`. **Regla de supervisión:** cualquier código que abra un cursor manual contra `connections[alias]` debe usar `with connections[alias].cursor() as cursor:`, nunca guardar el cursor o la conexión en una variable de instancia/módulo que sobreviva la request.

### Migraciones que bloquean tablas grandes

- **`ACCESS EXCLUSIVE` en operaciones DDL:** `AddField`, `AlterField` y `RemoveField` toman ese lock brevemente sobre la tabla completa. En PostgreSQL 11+, `AddField` con un default no-volátil (como `default=''` o `default=0`) es solo un cambio de metadatos — instantáneo, sin reescribir filas. Un default *volátil* (ej. `default=timezone.now`) sí obliga a reescribir cada fila con el lock tomado durante toda la operación — evitarlo en tablas que ya tengan datos.
- **`atomic = False` para índices concurrentes:** Django exige `atomic = False` en el archivo de migración para poder usar `AddIndexConcurrently`/`RemoveIndexConcurrently` (`django.contrib.postgres.operations`), que crean el índice con `CREATE INDEX CONCURRENTLY` — sin bloquear escrituras, a cambio de tardar más y no poder ir dentro de una transacción. Un `AddIndex` normal es aceptable mientras la tabla sea pequeña; en una tabla con millones de filas, `AddIndexConcurrently` es obligatorio.
- **Separación esquema/datos ya exigida en la §6** de esta skill — es la misma regla que evita bloquear una tabla grande con un `RunPython` masivo dentro de la misma transacción que un `ALTER TABLE`.

---

## 11. Alertas y Monitoreo en Producción

Métricas que vale la pena vigilar, y por qué suelen importar en este tipo de arquitectura:

| Métrica | Por qué importa | Umbral orientativo |
|---|---|---|
| **Cache hit ratio** (`pg_stat_database`: `blks_hit / (blks_hit + blks_read)`) | Sin réplica de lectura, toda la carga de lectura pública golpea la misma instancia. | > 99% deseable; < 90% sostenido indica que el `shared_buffers` es chico para el working set. |
| **Conexiones activas vs. `max_connections`** | Varios workers de aplicación más workers de tareas en segundo plano, más cualquier pool hacia sistemas externos, pueden agotar el límite bajo carga simultánea. | Alertar sobre 80% de `max_connections`. |
| **`n_dead_tup` / última corrida de autovacuum** (`pg_stat_user_tables`) | Directamente relevante si hay una tarea periódica de borrado en cascada (ver §9). | Alertar si `n_dead_tup` > 10% de `n_live_tup` sin autovacuum reciente. |
| **Locks en espera** (`pg_stat_activity` con `wait_event_type = 'Lock'`) | Señal temprana de contención — si el proyecto no usa `select_for_update` en ningún lugar, cualquier lock esperando por más de unos segundos es anómalo y merece investigación inmediata. | Cualquier espera > 5s en producción. |
| **Latencia y tasa de error de conexiones a sistemas externos** | Cualquier dependencia externa de solo lectura con timeout corto puede degradar en cascada a los endpoints que dependen de ella. | Alertar sobre una tasa de error sostenida, no solo picos puntuales. |
| **Throttling de DRF activándose de más** | Si un scope (anónimo, login, registro) se agota seguido en producción, o es tráfico legítimo creciendo (subir el límite) o es un intento de abuso (investigar IPs). | Revisar si algún scope se satura consistentemente, no solo en picos puntuales. |
| **Tamaño de tablas de auditoría de solo-inserción** | Candidatas a partición (§9) — su tasa de crecimiento es la señal que decide *cuándo* particionar, no una fecha arbitraria. | Revisar tendencia mensual, no un valor absoluto. |

**Cómo detectarlo temprano sin herramientas nuevas:** las consultas de `pg_stat_activity`, `pg_stat_user_tables` y `pg_stat_database` de esta sección corren con SQL plano — no requieren instalar nada, solo un cron/dashboard que las corra periódicamente y grafique la tendencia. Herramientas dedicadas (pgAdmin, Datadog, `pg_stat_statements` para top-N queries por tiempo total) son la evolución natural una vez que el proyecto tenga tráfico real que justifique el costo de operarlas.

---

## 12. Seguridad de Datos: PII y Retención

### Qué datos personales maneja este tipo de proyecto, en concreto

```python
Cliente.email                    # EmailField, unique=True
Cliente.identificador_fiscal     # CharField — identificador fiscal
Cliente.razon_social             # CharField — puede ser nombre de persona natural
Representante.documento_identidad  # CharField — documento de identidad
Representante.telefono           # CharField
Representante.correo             # EmailField
```

Este tipo de campos son datos de identificación fiscal y personal de personas naturales o representantes legales — PII real, no de laboratorio.

### Cuándo cifrar campos, y qué evaluar antes de decidirlo

Si estos campos no están cifrados a nivel de columna, es una decisión implícita que vale la pena hacer explícita al supervisar el modelo:

- **Cifrado a nivel de base de datos (`pgcrypto`, ej. `django-pgcrypto-fields`):** el cifrado/descifrado corre *dentro* de Postgres, así que la clave viaja en cada consulta y puede quedar expuesta en `pg_stat_activity` o en los logs de queries si se loguea el SQL completo. Evitar si el modelo de amenaza incluye a alguien con acceso de solo-lectura a los logs del servidor de base de datos.
- **Cifrado a nivel de aplicación (`django-fernet-fields`, AES simétrico vía la librería `cryptography`):** el cifrado ocurre en el proceso de la aplicación, antes de que el dato salga hacia Postgres — la clave nunca la ve la base. Es la opción recomendada si se decide cifrar, precisamente porque separa "quien administra la base" de "quien puede leer el dato en claro".
- **Trade-off a evaluar antes de elegir:** identificadores como un documento de identidad o un identificador fiscal normalmente hay que poder **buscar por igualdad exacta**; cifrar una columna con cifrado no-determinístico (el correcto para PII) impide indexarla para búsqueda exacta sin trabajo adicional (un índice sobre un hash determinístico aparte). Es una decisión de costo/beneficio que corresponde a quien es responsable del dato, no algo que un cambio de modelo deba decidir unilateralmente — si se pide cifrar, **preguntar explícitamente** cuál es el modelo de amenaza antes de elegir la técnica (misma regla de la §7).
- Las contraseñas de usuario son un caso distinto y ya resuelto por el framework de autenticación (hash con Argon2 u otro algoritmo dedicado a credenciales) — no confundir con el cifrado de PII de negocio.

### Retención y borrado — patrón recomendado

Una política de retención automatizada como la siguiente es un buen patrón a imitar para cuentas o registros que quedaron huérfanos sin decisión:

```python
@shared_task
def eliminar_cuentas_no_verificadas(dias: int = 7) -> int:
    """Borra las cuentas que nunca completaron la verificación, pasados `dias` desde su creación."""
    limite = timezone.now() - timedelta(days=dias)
    queryset = Cliente.objects.filter(
        verificado=False,
        created_at__lt=limite,
    ).exclude(
        estatus__in=[Cliente.Estatus.RECHAZADO, Cliente.Estatus.EN_REVISION],
    )
    cantidad = queryset.count()
    queryset.delete()  # en cascada: Representante, Verificacion, HistorialEstatus...
    return cantidad
```

Regístrala como tarea periódica y expónla también como comando de gestión para ejecución manual/cron.

**Por qué es un buen patrón de retención a imitar:**
1. **Alcance explícito y documentado en el propio código** (`verificado=False`, `dias=7`) — no una regla implícita en la cabeza de alguien.
2. **Excluye deliberadamente lo que ya fue evaluado** (`RECHAZADO`/`EN_REVISION`): borrar por antigüedad no es "borrar todo lo viejo", es "borrar lo que quedó huérfano sin que nadie tomara una decisión sobre ello".
3. **Doble camino de ejecución** (tarea periódica + comando manual) — nunca confiar solo en que la tarea periódica corra.
4. **Cascada real de PostgreSQL** (`on_delete=CASCADE`), no un `for` en Python borrando fila por fila — correcto y ya cubierto por la matriz de la §4.

**Si el proyecto necesitara una política de retención sobre datos *ya verificados* (no huérfanos)** — por ejemplo, "borrar el documento de identidad N años después de que una entidad deje de estar activa" — el mismo patrón aplica, pero con una diferencia importante: probablemente no se puede hacer un `DELETE` completo (puede ser necesario conservar el registro de que existió, solo sin el dato personal). Ahí el patrón correcto es **anonimizar, no borrar**: poner los campos PII en blanco/hash y dejar el resto de la fila (trazabilidad, estatus, fechas) intacto — una migración de datos con el mismo cuidado de idempotencia y reversibilidad de la §6, más una decisión explícita de qué campos se anonimizan (volver a la §7: preguntar, no inferir).

---

## 13. Cómo se combinan estas prácticas en un caso compuesto

Cómo las secciones 9-12 suelen aplicarse juntas, en la práctica, dentro de una arquitectura Onion multi-base:

### La capa de dominio como el único lugar que sabe "qué es válido"

El patrón Onion obliga a que la lógica de correspondencia entre entidades (buscar catálogo, resolver relación, calcular derivado) sea reutilizable por la migración de backfill **y** por un comando de reintento manual **y** por el serializer, sin duplicarse. Esa misma disciplina es la que hace posible escribir una política de retención (§12) o un backfill (§6) sin miedo a que la migración y el comando manual diverjan en su criterio — la regla de "una sola función, varios llamadores" de la arquitectura Onion es, en la práctica, la misma regla que previene bugs de integridad de datos.

### Un `Router` de base externa: aislar el riesgo de una base que no controlas

La integración de solo lectura con un sistema externo suele aplicar, sin nombrarlas así, varias prácticas de esta skill:
- **Connection pooling deliberado** (§9): `CONN_MAX_AGE=0` porque es una base ajena — no hay pooling que valga la pena mantener para una conexión que puede desaparecer.
- **Ausencia de transacciones cruzadas** (§10): como es una base distinta, no puede envolverse en el mismo `transaction.atomic()` que la base propia — el propio motor de Postgres lo impediría. El patrón correcto es consultar el sistema externo primero (fuera de cualquier transacción de escritura) y **después**, en una operación separada, persistir el resultado en la base propia. Nunca mezclar un `cursor()` sobre la base externa dentro de un `transaction.atomic()` que también escribe en la base propia — no hay 2PC (two-phase commit) configurado entre ambas, así que una mitad podría confirmarse y la otra no.
- **Monitoreo de una dependencia externa** (§11): la latencia/tasa de error de esa conexión específica suele ser la métrica más urgente de vigilar de todo el backend, porque es la que puede fallar por razones completamente fuera del control del equipo.
- **PII que no es del proyecto** (§12): las tablas espejo de un sistema externo contienen PII de ese sistema, no del proyecto propio — este proyecto no decide su política de retención ni de cifrado; eso es responsabilidad del sistema dueño de esa base. La regla de supervisión es la inversa de la §12: nunca copiar más campos del sistema externo a la base propia de los estrictamente necesarios para operar.

### Dónde se repetiría el patrón de retención de §12 si el proyecto crece

Si en el futuro se agregan más flujos de "registro a medio completar" (un borrador que nadie termina de enviar, una propuesta abandonada), el mismo patrón de `eliminar_cuentas_no_verificadas` — alcance explícito, exclusión de lo ya evaluado, doble camino tarea/comando — es la plantilla a copiar, no a reinventar.
