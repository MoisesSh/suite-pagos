---
name: testing-backend-django
description: Convenciones de testing del backend — TestCase/APITestCase nativos de Django (sin pytest), factories propias que pasan por servicios reales, aislamiento de caché de throttling, y mocking de la integración con RECAUDACION.
---

# Testing Backend Django

Skill para escribir tests que siguen exactamente el estilo ya establecido en el proyecto. **No introduzcas pytest, factory_boy, ni fixtures JSON** — el proyecto usa deliberadamente el framework nativo de Django/DRF.

---

## Ubicación y estructura

Sin carpeta `tests/` unificada a nivel de proyecto — cada app decide:

```
apps/conatel/tests.py         (7 tests)
apps/inversor/tests.py        (3 tests)
apps/operador/tests.py        (32 tests)
apps/users/tests.py           (13 tests)
apps/shared/tests/
  ├── __init__.py
  ├── base.py                 (BaseAPITestCase — clase base compartida)
  ├── factories.py            (funciones de creación de objetos de prueba)
  ├── test_api.py             (8)
  ├── test_cobertura_api.py   (12)
  ├── test_geo.py             (16)
  ├── test_seguridad.py       (11)
  └── test_services.py        (18)
```

`shared` es la única app con carpeta `tests/` (por volumen); las demás usan un único `tests.py`. Sigue ese criterio: convierte `tests.py` en carpeta `tests/` solo cuando el archivo se vuelve difícil de navegar, no de entrada.

---

## Framework: Django/DRF nativo, sin pytest

- **No hay pytest** — no está en `requirements.txt`, no hay `pytest.ini` ni `conftest.py`. No lo agregues sin discutirlo con el equipo primero; sería un cambio de herramienta, no solo de estilo.
- Clases base: `django.test.TestCase`, `django.test.SimpleTestCase`, `django.test.RequestFactory`, y `rest_framework.test.APITestCase` para tests de endpoints.
- Se corren con:

```bash
python manage.py test
```

No hay `settings_test.py` separado — usa la configuración normal de `FitVen/settings.py` con overrides puntuales vía `@override_settings` (ver caché, abajo).

---

## Factories — funciones, no clases `factory_boy`

`apps/shared/tests/factories.py` expone **funciones simples** (`crear_usuario`, `crear_conatel`, `crear_servicio`, `crear_proyecto`, etc.), no `factory_boy`. Usan `get_or_create` o, cuando el objeto necesita pasar por validaciones reales (ej. un usuario completo con perfil), llaman al **service de aplicación real** en vez de crear con el ORM directo:

```python
def crear_usuario(**overrides):
    defaults = {...}
    defaults.update(overrides)
    return RegistroService.crear_usuario(**defaults)   # mismo camino que producción
```

**Por qué importa**: si creas un usuario de prueba con `Usuario.objects.create(...)` directo, te saltas las validaciones y side-effects (trazabilidad, `DatosOperador` asociado, evento `usuario_registrado`) que sí ocurren en producción, y el test puede pasar por razones equivocadas. Usa las factories existentes o, si necesitas una nueva, síguelas por el mismo service — no por el ORM crudo, salvo que estés probando explícitamente un caso de borde del propio ORM/modelo.

---

## Aislamiento de caché de throttling (`BaseAPITestCase`)

**Contexto crítico** (commit `91b4fe6`, `fix(tests): aislar la caché de los tests de la de la aplicación`): el throttling de DRF guarda sus contadores en Redis, base 1 — la misma que usa la app corriendo en desarrollo/staging. Antes de este fix, `cache.clear()` en `setUp()` borraba contadores de throttling **reales** de usuarios reales, y además dejaba residuos entre corridas de test que agotaban cupos (ej. `registro: 20/hour`) y hacían fallar tests subsecuentes sin relación aparente.

Solución en `apps/shared/tests/base.py`:

```python
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'tests-throttling',
    },
})
class BaseAPITestCase(APITestCase):
    def setUp(self):
        cache.clear()
        super().setUp()
```

**Toda clase de test que ejercite endpoints con throttling debe heredar de `BaseAPITestCase`**, no de `APITestCase` directo — de lo contrario corre el riesgo de tocar la caché de Redis compartida otra vez.

Django fusiona `@override_settings` de subclases, así que una clase hija puede añadir sus propios overrides sin perder el de caché:

```python
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class RegistroAPITests(BaseAPITestCase):
    ...
```

---

## Mocking de integraciones externas

El único servicio con I/O verdaderamente externo es `HabilitacionService` (consulta la BD ajena RECAUDACION, ver [[integracion-bd-recaudacion]]). Los tests **nunca tocan esa BD real** — mockean el service:

```python
from unittest.mock import patch

class HabilitacionViewTests(BaseAPITestCase):
    @patch.object(HabilitacionService, 'consultar')
    def test_recaudacion_caida_devuelve_503(self, mock_consultar):
        mock_consultar.side_effect = RecaudacionNoDisponible('BD no configurada')
        response = self.client.get('/api/operador/habilitacion/')
        self.assertEqual(response.status_code, 503)
```

Aplica el mismo criterio a cualquier integración externa nueva (otra BD ajena, servicio HTTP de terceros, etc.): mockea en el punto de entrada del service (`patch.object(Servicio, 'metodo')`), no la librería de bajo nivel (`psycopg2`, `requests`), para que el test no dependa de detalles de implementación.

---

## Cobertura actual (referencia, no objetivo fijo)

120 métodos `def test_` en total. Áreas cubiertas, por nombre de clase real:

| Área | Clase de test | Qué verifica |
|---|---|---|
| Auth + cookies JWT | `RefreshCookieTests` | login/refresh/logout, blacklist de refresh token |
| Bloqueo de edición post-verificación | `BloqueoEdicionVerificadoTests` | status 409 al intentar editar perfil ya verificado |
| Auditoría de IP anti-spoofing | `ClientIPTests` | resolución de IP real detrás de proxy (`TRUSTED_PROXY_COUNT`) |
| Matchmaking restringido | `MatchmakingSeguridadTests` | solo usuarios verificados pueden solicitar/responder |
| Geografía | `test_geo.py` (varias clases) | catálogo territorial, endpoints en cascada |
| Integración RECAUDACION | `apps/operador/tests.py` (32 tests) | estados de habilitación, caso `RecaudacionNoDisponible → 503` |

---

## Ejemplo idiomático completo (patrón canónico)

Basado en `apps/shared/tests/test_seguridad.py`:

```python
from apps.shared.tests.base import BaseAPITestCase
from apps.shared.tests import factories


class BloqueoEdicionVerificadoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.usuario = factories.crear_usuario(estatus=Usuario.Estatus.VERIFICADO)

    def test_rechazado_si_puede_editar(self):
        self.client.force_authenticate(self.usuario)
        response = self.client.patch('/api/perfil/', {'nombre': 'Nuevo'})
        self.assertEqual(response.status_code, 409)

    def test_verificado_no_edita_perfil_de_otro(self):
        otro = factories.crear_usuario()
        self.client.force_authenticate(otro)
        response = self.client.patch(f'/api/perfil/{self.usuario.id}/', {'nombre': 'Hackeo'})
        self.assertEqual(response.status_code, 403)
```

Patrón: `BaseAPITestCase` + `factories`, `force_authenticate` en vez de login real por HTTP, un test de éxito y uno de error **por invariante** (no solo "camino feliz"), aserciones de `status_code` explícitas y numéricas (no símbolos de `status.HTTP_*` mezclados con literales — usa lo que ya predomine en el archivo que estés extendiendo).

---

## Entorno local — problema conocido, no del código

En este entorno, `python manage.py test` falla por: falta `django-redis` instalado en `.venv` (está en `requirements.txt` pero no instalado), y el usuario de Postgres no tiene permiso `CREATEDB` para crear la base de test. Esto es un problema de setup del entorno, no de los tests — antes de reportar un test como roto, verifica que el entorno local pueda siquiera levantar la app.

---

## Comandos

### 1. Escribir un test nuevo

```
@skill escribe un test para [endpoint/service]
```

1. Hereda de `BaseAPITestCase` (no `APITestCase` directo) si el test toca cualquier vista con throttling.
2. Usa `factories.crear_xxx()` existentes; si no existe la que necesitas, créala pasando por el service real, no por `Model.objects.create()` directo.
3. Si el test ejercita `HabilitacionService` u otra integración externa, mockéala con `patch.object` en el punto de entrada del service.
4. Escribe al menos un test de éxito y uno de error por invariante nueva que introduzcas.

### 2. Diagnosticar un test que falla solo en CI o solo localmente

```
@skill por qué falla [test] en [entorno]
```

Primero descarta el problema conocido de entorno (django-redis faltante / permiso CREATEDB). Si persiste, revisa si la clase hereda de `BaseAPITestCase` — un test que use `APITestCase` directo puede estar leyendo/escribiendo en la caché Redis compartida y arrastrar estado de otra corrida.
