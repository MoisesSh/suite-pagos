---
name: arquitectura-onion-feature-scream
description: Arquitectura Onion + Feature-Based + Scream del backend Django (apps/{domain,application,infraestructure,api}). Explica capas, reglas de dependencia, convención de nombres, y dónde crear cada tipo de código nuevo.
---

# Arquitecto Onion-Feature-Scream (Backend)

Skill para trabajar con la arquitectura del backend Django, basada en Scream + Feature-Based + Onion — la misma familia de patrones que usa el frontend (`fitelven_frontend/.claude/skills/arquitecto-scream-feature-onion`), adaptada a Django.

---

## Visión general

`apps/` grita el dominio del negocio, no la tecnología: `shared`, `users`, `operador`, `inversor`, `gobierno`, `conatel`. No hay carpetas `models/`, `views/`, `serializers/` a nivel raíz — cada perfil de usuario del sistema (operador de telecomunicaciones, inversor, ente de gobierno, staff CONATEL) es una app de primer nivel.

Dentro de cada app, las capas van de adentro hacia afuera (Onion):

```
domain → application → infrastructure → api
```

**Hallazgo clave — no lo ignores al crear código nuevo:** la arquitectura onion completa solo está 100% poblada en `shared`. Las apps feature (`users`, `operador`, `inversor`, `gobierno`, `conatel`) tienen las carpetas `domain/`, `application/`, `infraestructure/` creadas como placeholders del patrón, pero casi siempre **vacías**. La lógica de negocio transversal vive centralizada en `apps.shared`, y las apps feature son mayoritariamente una capa `api/` delgada que la consume. Solo `operador` tiene lógica propia real (`application/habilitacion.py`, `infraestructure/recaudacion_models.py`), porque es la única con una integración externa genuina (ver [[integracion-bd-recaudacion]]).

**No fuerces a crear `domain/`/`application/` en una app feature si la lógica es genuinamente transversal o no existe todavía.** Antes de añadir un service nuevo en `apps/operador/application/`, pregúntate si en realidad pertenece a `apps/shared/application/services/` porque lo van a necesitar otras apps.

**No existe capa de "repository"** (puerto/adaptador explícito como en el frontend `repo-[nombre].ts`). El acceso a datos es Django ORM directo desde `application/` y `api/`. No inventes una capa de repositorio — no es el patrón de este proyecto.

---

## Estructura real por app

```
apps/
├── shared/                          ← núcleo del dominio (kernel compartido)
│   ├── domain/
│   │   ├── models.py                (TODOS los modelos ORM del sistema, ~900 líneas)
│   │   ├── events.py                (django.dispatch.Signal — eventos de dominio)
│   │   ├── permissions.py           (BasePermission custom, compartidos por toda la plataforma)
│   │   ├── habilitacion.py          (TextChoices EstadoHabilitacion)
│   │   ├── geo.py                   (funciones puras, sin ORM)
│   │   └── rif.py                   (funciones puras, sin ORM — rif_canonico/rif_presentable)
│   ├── application/
│   │   └── services/
│   │       ├── dashboard.py, historial.py, matchmaking.py, modelo_negocio.py,
│   │       │   notificacion.py, proyecto.py, trazabilidad.py, verificacion.py,
│   │       │   verificacion_email.py
│   ├── infrastructure/               ← ÚNICA app que escribe el nombre correcto en inglés
│   │   ├── receivers.py             (@receiver — conecta events.py con tasks.py)
│   │   └── tasks.py                 (@shared_task de Celery)
│   ├── api/
│   │   ├── serializers.py           (~22 clases)
│   │   ├── views.py                 (generics.*, views.APIView)
│   │   ├── urls.py
│   │   └── utils.py
│   ├── models.py                    ← re-exporta domain/models.py (ver nota abajo)
│   ├── migrations/
│   └── tests/                       (ver [[testing-backend-django]])
│
├── users/                            ← feature: auth y perfil
│   ├── domain/                      (vacío, solo __init__.py)
│   ├── application/services.py      (RegistroService + excepciones propias)
│   ├── infraestructure/             (vacío — OJO: con "e" extra, ver nota de naming)
│   ├── api/ (serializers.py, views.py, urls.py, cookies.py)
│   └── tests.py
│
├── operador/                         ← única app feature con capas realmente pobladas
│   ├── domain/                      (vacío)
│   ├── application/habilitacion.py  (HabilitacionService — SQL crudo contra RECAUDACION)
│   ├── infraestructure/recaudacion_models.py  (modelos managed=False, solo lectura)
│   ├── api/ (serializers.py, views.py, urls.py)
│   └── tests.py
│
├── inversor/, gobierno/, conatel/    ← domain/, application/, infraestructure/ VACÍOS
│   └── api/ (serializers.py, views.py, urls.py) — delegan a apps.shared.application.services.*
│       o a servicios de otra app feature (ej. conatel importa HabilitacionService de operador)
```

### `models.py` en la raíz de `shared`

`apps/shared/models.py` re-exporta `domain/models.py`. Es un truco necesario: Django descubre modelos por convención en `<app>.models`, y así `domain/` se mantiene puro (sin acoplarse a que Django lo busque en un path específico) sin romper esa convención. Si creas una app nueva con modelos propios, replica este patrón.

---

## Capas y dependencias (Onion) — reglas confirmadas por código real

La flecha significa "depende de" → **siempre apunta hacia adentro**. Confirmado con grep de imports reales, no solo teoría:

| Capa | Puede importar de | Evidencia real |
|---|---|---|
| `domain/` | Solo otros módulos de `domain/` (propio o `shared.domain` si eres una app feature) | `permissions.py` → `domain.models`. **0 violaciones** hacia application/infraestructure/api encontradas. |
| `application/` | `domain/` (propio o de `shared`), y otros servicios de `application/` | `matchmaking.py` → `historial.py`; `users/application/services.py` → 3 services de `shared` |
| `infrastructure/` | `application/` y `domain/` | `tasks.py` → `application.services.verificacion_email` + `domain.models`; `receivers.py` → `application.services.notificacion` + `domain.events` + `infrastructure.tasks` |
| `api/` | `application/services/*` para lógica con reglas de negocio. ORM directo **permitido** para lecturas/escrituras simples (listados, `get_or_create`) | `shared/api/views.py` usa `.objects.` directo para querysets de `ListAPIView` y filtros geo en cascada, pero delega a `MatchmakingService`/`ProyectoService`/`ModeloNegocioService` cuando hay reglas de negocio |
| `api/` de apps feature | `apps.shared.domain.*`, `apps.shared.application.services.*`, `apps.shared.api.serializers` (reusar `MensajeRespuestaSerializer`), y entre sí | `conatel/api/views.py` importa `HabilitacionService` de `operador`; `inversor`/`gobierno` importan `bloquear_si_verificado` de `users.application.services` |

### Patrón domain → infrastructure: eventos + signals + Celery

No se llama `.delay()` directo desde las vistas (con una única excepción documentada: `apps/users/api/views.py` para reenvío manual de verificación). El flujo estándar es:

```
application/services/xxx.py
  → events.evento_x.send(sender=XxxService, **kwargs)     Django Signal (domain/events.py)
    ↓
infrastructure/receivers.py
  → @receiver(events.evento_x)
    def despachar_algo(sender, **kwargs):
        Notificacion.objects.create(...)                    # side-effect in-app síncrono
        transaction.on_commit(lambda: tasks.algo.delay(...)) # Celery solo tras commit
```

`transaction.on_commit()` es obligatorio para que el worker de Celery nunca vea datos sin confirmar. Comentario real en el código: *"La capa application emite estos eventos; la capa infrastructure los escucha. Así las dependencias apuntan hacia adentro (Onion)."*

Los receivers se conectan en `AppConfig.ready()`. Solo `SharedConfig.ready()` hace esto (única app con signals propios):

```python
class SharedConfig(AppConfig):
    def ready(self):
        import apps.shared.infrastructure.receivers  # noqa: F401
```

Ver [[uso-librerias-backend]] para el detalle de Celery/tasks.

---

## ⚠️ Naming inconsistente: `infraestructure` vs `infrastructure`

Es un **typo histórico**, no una regla a seguir:

- `apps/shared/infrastructure/` — correcto en inglés.
- `apps/{conatel,gobierno,inversor,operador,users}/infraestructure/` — con "e" extra (mal escrito).

Al crear una app nueva, **no elijas al azar**. Si tienes duda, revisa cómo se llama la carpeta en la app más parecida a la que vas a tocar, y si vas a crear una app completamente nueva, usa `infrastructure` (la forma correcta) y avisa que las demás tienen el typo — no lo repliques por consistencia ciega salvo que el equipo decida homogeneizar en una migración aparte.

---

## Convención de nombres (con ejemplos reales)

| Elemento | Archivo | Clase/función | Ejemplo real |
|---|---|---|---|
| Modelo ORM | `domain/models.py` (todos juntos, no un archivo por modelo) | `class Nombre(BaseModel)` o `(AbstractUser)` | `class Perfil(BaseModel)`, `class Usuario(AbstractUser, BaseModel)` |
| Modelo base abstracto | `domain/models.py` | `class BaseModel(models.Model)` | UUID v7 + `created_at`/`updated_at`, `abstract = True` |
| Choices internos | dentro del modelo | `class Estatus(models.TextChoices)` | `Perfil.TipoPerfil`, `Verificacion.Estatus`, `Usuario.Estatus` |
| Lógica pura de dominio (sin ORM) | `domain/[tema].py` | funciones sueltas, snake_case | `domain/rif.py::rif_canonico()`, `domain/geo.py::normalizar()` |
| Eventos | `domain/events.py` | `nombre_evento = django.dispatch.Signal()` | `usuario_registrado`, `solicitud_reunion_creada` |
| Permisos custom | `domain/permissions.py` | `class IsXxx(BasePermission)` | `IsConatelAdmin`, `IsVerificado` |
| Servicio de aplicación | `application/services/[tema].py` | `class XxxService` con métodos `@staticmethod` | `VerificacionService`, `MatchmakingService`, `HabilitacionService` |
| Excepciones de dominio/aplicación | junto al servicio que las usa | `class XxxError(Exception)` | `PerfilBloqueadoError`, `RecaudacionNoDisponible`, `EmailNoVerificadoError` |
| Resultado inmutable de servicio | junto al servicio | `@dataclass(frozen=True) class ResultadoXxx` con `.to_dict()` | `ResultadoHabilitacion` |
| Tarea async | `infrastructure/tasks.py` | `@shared_task` función snake_case | `notificar_bienvenida`, `reenviar_verificacion_email` |
| Receiver | `infrastructure/receivers.py` | `@receiver(events.x)` función `despachar_xxx` | `despachar_bienvenida` |
| Modelo espejo solo-lectura (BD externa) | `infraestructure/recaudacion_models.py` | `class Xxx(models.Model)` con `managed = False` | `UsuarioRecaudacionWeb`, `OperadorRecaudacion` |
| Serializer | `api/serializers.py` (todos juntos por app) | `class XxxSerializer(serializers.ModelSerializer\|Serializer)` | Ver [[patrones-drf-implementacion]] |
| Vista | `api/views.py` | `class XxxView(views.APIView)` o `class XxxListView(generics.ListAPIView)` | Ver [[patrones-drf-implementacion]] |
| URLs de app | `api/urls.py` | `app_name = '<app>'`, lista `urlpatterns` | `app_name = 'shared'`, `app_name = 'operador'` |
| AppConfig | `apps.py` | `class XxxConfig(AppConfig)` | `SharedConfig` (con `ready()`), `OperadorConfig` (sin `ready()`) |

> **Nota:** a diferencia del frontend, aquí `models.py`, `serializers.py`, `views.py` son **un archivo único por capa y por app**, no un archivo por entidad. Solo divide en submódulos (`services/` como carpeta en vez de archivo) cuando el archivo crece demasiado — ya es el caso de `application/services/` en `shared`.

---

## INSTALLED_APPS y enrutamiento raíz

```python
INSTALLED_APPS = [
    # django.contrib.*: auth, contenttypes, sessions, messages, staticfiles
    # Third-party: rest_framework, rest_framework_simplejwt,
    #   rest_framework_simplejwt.token_blacklist, corsheaders,
    #   django_filters, drf_spectacular, django_celery_beat
    # Project apps — shared PRIMERO porque es dueño del modelo Usuario:
    'apps.shared', 'apps.users', 'apps.operador',
    'apps.inversor', 'apps.gobierno', 'apps.conatel',
]
```

```python
# FitVen/urls.py — un path por feature, todo bajo /api/
urlpatterns = [
    path('api/', include('apps.shared.api.urls')),          # sin prefijo propio: catálogos públicos
    path('api/auth/', include('apps.users.api.urls')),
    path('api/operador/', include('apps.operador.api.urls')),
    path('api/inversor/', include('apps.inversor.api.urls')),
    path('api/gobierno/', include('apps.gobierno.api.urls')),
    path('api/conatel/', include('apps.conatel.api.urls')),
]
# + swagger/redoc solo si settings.EXPOSE_API_DOCS (default: solo DEBUG)
```

`shared` no tiene prefijo propio (`api/` a secas) — es deliberado: expone catálogos y vitrina pública sin marcar "shared" en la ruta.

---

## Plantillas de archivos base

### Modelo de dominio — `domain/models.py`

```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Perfil(BaseModel):
    class TipoPerfil(models.TextChoices):
        OPERADOR = 'operador', 'Operador de Telecomunicaciones'
        # ...

    tipo_perfil = models.CharField(max_length=20, choices=TipoPerfil.choices, unique=True)
```

### Servicio de aplicación — `application/services/[tema].py`

```python
class MatchmakingService:
    @staticmethod
    @transaction.atomic
    def solicitar(usuario, operador_destino, servicio, prioridad='media', mensaje=''):
        match, created = Matchmaking.objects.get_or_create(...)
        if created:
            events.solicitud_reunion_creada.send(sender=MatchmakingService, matchmaking=match)
        return match
```

### Vista feature delegando a `application/` de otra app — `api/views.py`

```python
class MiHabilitacionView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            resultado = HabilitacionService.sincronizar(request.user)
        except RecaudacionNoDisponible as exc:
            return Response({'error': str(exc)}, status=503)
        return Response(HabilitacionSerializer(resultado.to_dict()).data)
```

### `apps.py`

```python
class OperadorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.operador'
    # sin ready() — no tiene signals propios
```

### `api/urls.py`

```python
app_name = 'operador'
urlpatterns = [
    path('habilitacion/', MiHabilitacionView.as_view(), name='mi_habilitacion'),
]
```

Para plantillas de `serializers.py`/`views.py`, ver [[patrones-drf-implementacion]].

---

## Reglas de validación Onion

| Regla | Violación | Mensaje |
|---|---|---|
| **R1** | `domain/` importa de `application/`, `infrastructure/`/`infraestructure/`, `api/`, o de Django REST Framework | ❌ **R1**: Domain no puede importar de capas externas ni de DRF. Solo modelos ORM base, TextChoices, funciones puras y Signals. |
| **R2** | `application/` importa de `infraestructure/` o `api/` | ❌ **R2**: Application no puede importar de infraestructure ni api. Solo de `domain/` y de otros `application/services/*`. |
| **R3** | `api/` instancia lógica de negocio compleja inline en vez de delegar a un `Service` | ⚠️ **R3**: Si la vista tiene más de una regla de negocio no trivial (validaciones cruzadas, efectos secundarios, transacciones), extráela a `application/services/`. |
| **R4** | Un service dispara Celery con `.delay()` fuera de un `transaction.on_commit()` | ❌ **R4**: Todo despacho de Celery iniciado por un cambio de estado en la misma transacción debe envolverse en `transaction.on_commit()` para evitar que el worker vea datos sin commitear. |
| **R5** | Se crea una capa de "repository" (`repo_xxx.py`) para abstraer el ORM | ❌ **R5**: Este proyecto no usa el patrón repository. El acceso a datos es ORM directo desde `application/` y `api/`. No la inventes. |
| **R6** | Se agrega lógica de negocio nueva en `apps/<feature>/application/` cuando en realidad es transversal | ⚠️ **R6**: Si más de una app feature la va a necesitar, va en `apps/shared/application/services/`, no en la app feature. |
| **R7** | Un modelo de BD externa (`recaudacion_models.py` u otro similar) no tiene `managed = False` | ❌ **R7**: Todo modelo que apunte a una base de datos ajena/externa debe declarar `managed = False` y quedar excluido de `allow_migrate` en su router. Ver [[integracion-bd-recaudacion]]. |
| **R8** | Se usa el nombre de carpeta `infraestructure` en una app **nueva** | ⚠️ **R8**: Es un typo histórico heredado, no la regla. En código nuevo usa `infrastructure` (correcto), salvo que el equipo decida homogeneizar explícitamente. |
| **R9** | Un archivo de la capa `api/` no sigue snake_case, o una clase no sigue PascalCase con sufijo (`View`, `Serializer`, `Service`) | ❌ **R9**: Sigue la tabla de convención de nombres de esta skill. |

---

## Comandos

### 1. Crear una feature/servicio nuevo

```
@skill crea el servicio [nombre] para la app [app]
```

**Flujo:**
1. Preguntar: *"¿Esta lógica es exclusiva de `[app]` o la van a necesitar otras apps?"* — si es transversal, va en `apps/shared/application/services/[tema].py`, no en la app feature.
2. Si el modelo de datos no existe, crearlo en `domain/models.py` de la app dueña (normalmente `shared`), heredando de `BaseModel`.
3. Crear el service en `application/services/[tema].py` con métodos `@staticmethod`, envolviendo en `@transaction.atomic` si hay múltiples escrituras.
4. Si el service dispara efectos secundarios (email, notificación), emitir un evento en `domain/events.py` y crear su receiver en `infrastructure/receivers.py` — no llamar `.delay()` directo desde el service salvo un caso ya excepcional y documentado.
5. Exponerlo vía `api/views.py` + `api/serializers.py` + `api/urls.py` siguiendo [[patrones-drf-implementacion]].

### 2. Validar una feature existente

```
@skill valida [modulo/servicio] en [app]
```

Aplica las reglas R1-R9 de esta skill y reporta violaciones con el archivo/línea exacto.

### 3. Decidir dónde vive código nuevo

```
@skill ¿dónde va [descripción de la lógica]?
```

Árbol de decisión:
```
¿Es un modelo/campo/regla de negocio pura, sin I/O?
├── Sí → domain/ (de shared si es transversal, de la app feature si es exclusiva)
└── No, ¿orquesta modelos + transacciones + puede disparar eventos?
    ├── Sí → application/services/
    └── No, ¿es I/O externo (Celery, email, BD ajena, signals)?
        ├── Sí → infrastructure/ (o infraestructure/ si sigues el typo de la app existente)
        └── No → api/ (serializer, view, urls)
```
