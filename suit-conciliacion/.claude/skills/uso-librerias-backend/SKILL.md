---
name: uso-librerias-backend
description: Cómo se configuran y usan realmente Celery, Redis/caché, drf-spectacular, django-filter, argon2 y corsheaders en el backend. La autenticación JWT/simplejwt tiene su propia skill.
---

# Uso de librerías (Backend)

Skill de referencia rápida para saber cómo está configurada e integrada cada librería de `requirements.txt` que tiene comportamiento no trivial en este proyecto. Para JWT/simplejwt ver [[autenticacion-permisos-jwt]]. Para el router de la BD externa RECAUDACION ver [[integracion-bd-recaudacion]] (es arquitectura de datos, no una "librería" per se).

---

## Celery

### Configuración (`FitVen/celery.py`)

```python
app.autodiscover_tasks(['apps.shared'], related_name='infrastructure.tasks')
```

**Solo autodescubre tasks en `apps.shared`** — es la única app con `infrastructure/tasks.py`. Si creas tasks en otra app, o las agregas a la lista de `autodiscover_tasks`, o (mejor, siguiendo el patrón actual) muévelas a `apps.shared.infrastructure.tasks` si son razonablemente transversales.

- Broker y result backend: Redis, base **0** (`redis://.../0`) — separada de la base de caché.
- Serializer: JSON.
- `CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'` — `django-celery-beat` está instalado y configurado, pero **no hay schedules periódicos definidos todavía**. Es infraestructura lista, no una feature en uso. Si necesitas una tarea periódica, créala vía el admin de Django (modelo `PeriodicTask`) o una migración de datos, siguiendo la documentación de `django-celery-beat` — no hay un ejemplo propio del proyecto que copiar todavía.

### Tasks reales (`apps/shared/infrastructure/tasks.py`)

6 tasks, todas con el mismo patrón:

```python
@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def notificar_bienvenida(usuario_id):
    try:
        usuario = Usuario.objects.get(pk=usuario_id)
    except Usuario.DoesNotExist:
        logger.warning('Usuario %s ya no existe, se omite notificación', usuario_id)
        return
    send_mail(...)
```

Todas: reciben IDs (no instancias, para ser serializables), reintentan automáticamente con backoff, y capturan `DoesNotExist` con un warning en vez de fallar la task — el usuario pudo haber sido borrado entre el `.send()` de la señal y la ejecución async.

### Cómo se disparan — casi nunca `.delay()` directo

**Patrón estándar**: `application/services/` emite un evento de dominio (`domain/events.py`), `infrastructure/receivers.py` lo escucha y despacha la task dentro de `transaction.on_commit()`. Ver el detalle completo en [[arquitectura-onion-feature-scream]] (sección "Patrón domain → infrastructure: eventos + signals + Celery").

**Única excepción documentada**: `apps/users/api/views.py` (`ReenviarVerificacionView`) llama `.delay()` directo desde la vista, porque es una acción explícita del usuario ("reenviar email"), no una consecuencia de un cambio de estado que necesite pasar por una transacción de escritura.

No repliques `.delay()` directo desde una vista salvo que sea genuinamente análogo a este caso (acción explícita, sin escritura de dominio asociada).

---

## Redis / caché

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',   # base 1 — distinta de Celery (base 0)
        'OPTIONS': {
            'IGNORE_EXCEPTIONS': True,        # falla abierto si Redis cae (documentado BE-04)
        },
    },
}
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True
```

**Uso real confirmado: exclusivamente para los contadores de throttling de DRF.** No hay ni un solo `cache.get`/`cache.set`/`@cache_page` en todo `apps/` para catálogos geográficos ni ninguna otra cosa de negocio.

⚠️ **No asumas que hay caché de negocio que invalidar** al modificar catálogos (geografía, servicios, etc.) — no existe. Si vas a introducir la primera caché de negocio real, ten en cuenta `IGNORE_EXCEPTIONS=True`: el proyecto ya decidió que el sistema debe seguir funcionando (sin caché) si Redis cae, en vez de devolver 500. Sigue ese mismo criterio de "falla abierto" para cualquier caché nueva.

Ver [[testing-backend-django]] para cómo se aísla esta caché de Redis en los tests (usa `LocMemCache` para no pisar contadores de throttling reales).

---

## drf-spectacular

```python
SPECTACULAR_SETTINGS = {
    ...
    'ENUM_NAME_OVERRIDES': {
        # necesario porque drf-spectacular no resuelve el acceso anidado a .choices
        # de un TextChoices definido dentro de una clase de modelo
        'EstatusUsuarioEnum': 'apps.shared.domain.models.Usuario.Estatus',
        # ... (uno por cada TextChoices reutilizado en más de un lugar)
    },
}
```

Expuesto solo condicionalmente (`FitVen/urls.py`):

```python
if settings.EXPOSE_API_DOCS:   # default: settings.DEBUG
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
    ]
```

**Regla al añadir un `TextChoices` nuevo que se reutilice en más de un modelo/serializer**: agrégalo a `ENUM_NAME_OVERRIDES` con un nombre explícito, o drf-spectacular generará nombres de enum colisionantes o genéricos (`Enum1`, `Enum2`) en el schema OpenAPI.

---

## django-filter

```python
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}
```

Configurado globalmente pero **sin ningún `FilterSet` custom en uso** — ver detalle y alternativa real (`get_queryset()` manual) en [[patrones-drf-implementacion]].

---

## argon2 / password hashers

```python
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',        # usado para hashear nuevas
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',        # fallback de lectura
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]
```

Argon2 es el hasher activo (primero en la lista = el que Django usa para crear/verificar hashes nuevos); los demás solo permiten leer/re-hashear passwords antiguos si migraste desde otro hasher. No reordenes esta lista sin entender que afecta la compatibilidad con hashes ya almacenados en la BD.

---

## corsheaders

```python
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
if settings.DEBUG and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOW_ALL_ORIGINS = True   # solo en desarrollo sin configurar
```

En producción, `CORS_ALLOWED_ORIGINS` debe venir siempre seteado por variable de entorno — el fallback a "permitir todo" solo aplica si `DEBUG=True`.

---

## Comandos

### 1. Añadir una tarea de Celery nueva

```
@skill crea la task de celery [nombre]
```

1. Colócala en `apps/shared/infrastructure/tasks.py` (a menos que tengas una razón fuerte para otra app — y si es así, agrega esa app a `autodiscover_tasks` en `FitVen/celery.py`).
2. Decora con `@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)`.
3. Recibe IDs, no instancias de modelo.
4. Captura `DoesNotExist` con `logger.warning`, no dejes que la task falle por una fila borrada.
5. Dispárala desde un `@receiver` en `infrastructure/receivers.py`, envuelta en `transaction.on_commit()` — no la llames `.delay()` directo desde una vista salvo que sea una acción explícita sin escritura de dominio asociada.

### 2. Añadir un enum/TextChoices que se reutiliza

```
@skill agrega el choices [nombre] a varios modelos
```

Recuerda registrar la entrada correspondiente en `ENUM_NAME_OVERRIDES` de `SPECTACULAR_SETTINGS` para que el schema OpenAPI no genere nombres genéricos o colisione.
