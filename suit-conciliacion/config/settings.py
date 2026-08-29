"""
Django settings for config project.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-qby3%!tvi4lj#ig2@%h3!pu+ba6b2in1h=u#mohr*$xvf$=g%a')

# SECURITY WARNING: don't run with debug turned on in production!
# Default False (auditoría de seguridad, Bloque #16 PLAN-DE-MEJORAS.md): un
# default inseguro acá era la causa raíz del fail-open de CORS de abajo —
# cualquier entorno que necesite DEBUG=True (dev/staging) debe pedirlo
# explícito por env, nunca asumirlo por omisión.
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# CORS_ALLOWED_ORIGINS es obligatorio y explícito, independiente de DEBUG —
# antes se abría CORS_ALLOW_ALL_ORIGINS automáticamente si DEBUG=True y esta
# lista estaba vacía (fail-open doble: DEBUG inseguro → CORS abierto
# inseguro, con CORS_ALLOW_CREDENTIALS=True reflejando el origen del
# atacante). Sin origins configurados, CORS simplemente no habilita ningún
# origen — ninguna app de navegador puede llamar a esta API con cookies.
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True  # el refresh token viaja en cookie HttpOnly

# Origen fijo del Developer Portal (suit-portal), permitido a embeber
# /api/docs/ y /api/schema/ por iframe (ver config/urls.py). Documentación
# interna, no un flujo de pago crítico (a diferencia del formulario de cobro
# del Orquestador) — alcanza con un origen fijo por env var, sin catálogo
# dinámico de dominios ni token firmado.
PORTAL_ORIGIN = env('PORTAL_ORIGIN', default='http://localhost:3001')

# Cifrado de campos sensibles (django-fernet-fields-v2) — cédula/teléfono del
# pagador y respuestas crudas del proveedor (auditoría de seguridad, Bloque
# #16). Clave propia, NUNCA la misma que SECRET_KEY (esta cifra datos en
# reposo, SECRET_KEY firma tokens/sesiones — mezclar ambos usos es
# exactamente lo que la separación de claves busca evitar). Lista (no un
# único valor): la primera clave cifra, todas se intentan al descifrar —
# permite rotar sin invalidar filas ya cifradas con la clave anterior.
# El default es una clave de desarrollo fija (no aleatoria en cada arranque:
# una clave nueva por proceso volvería indescifrable cualquier dato ya
# guardado) — producción DEBE fijar FERNET_KEYS por env, nunca usar este default.
FERNET_KEYS = env.list('FERNET_KEYS', default=['_0hH3FXmX6MHOcOJdUG-YxwiluUtQ_goo1UYVl822DQ='])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'drf_spectacular',
    'corsheaders',
    # Apps propias — shared primero porque no depende de nadie:
    'apps.shared',
    'apps.users',
    'apps.conciliacion',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Postgres propia (database-per-service) — sin FK cruzada con el Orquestador.
# Sin fallback a sqlite: un default silencioso acá fue la causa real de que
# un smoke test corriera contra una base distinta a la de Docker sin que
# nadie lo notara (Bloque #16, auditoría de seguridad). Fail-fast explícito
# en vez de dejar que Django recién falle más adelante con un error críptico
# de conexión.
if not env('DATABASE_URL', default=None):
    raise RuntimeError(
        'DATABASE_URL es obligatoria — sin fallback a sqlite. Configurala en '
        '.env o en el entorno (Postgres real, database-per-service).',
    )

DATABASES = {
    'default': env.db('DATABASE_URL'),
}

AUTH_USER_MODEL = 'users.Usuario'


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Email

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}


# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Login expuesto a fuerza bruta — mismo límite que el patrón de referencia.
        'login': '10/min',
        # Refresh legítimo del frontend interno de discrepancias: alto tráfico esperado.
        'refresh': '600/hour',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Suit Conciliación API',
    'DESCRIPTION': 'Servicio async de conciliación de pagos (matching BDV + ledger de doble entrada).',
    'VERSION': '1.0.0',
}


# --------------------------------------------------------------------------
# JWT (simplejwt) + cookie HttpOnly del refresh token
# --------------------------------------------------------------------------

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

JWT_REFRESH_COOKIE = {
    'NAME': 'refresh_token',
    'HTTPONLY': True,
    'SECURE': not DEBUG,
    'SAMESITE': 'Strict',
    'PATH': '/api/auth/',
}


# --------------------------------------------------------------------------
# Celery — consumidor directo de la cola RabbitMQ `pago.*`
# --------------------------------------------------------------------------

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='amqp://guest:guest@localhost:5672//')
# Sin result backend por defecto (research-stack-mensajeria.md): las tareas de
# Conciliación son fire-and-forget, el resultado no se consulta desde ningún
# lugar. No se agrega Redis solo para tener uno. La trazabilidad real vive en
# Postgres (EventoPagoRecibido.procesado_at, Discrepancia, TransaccionLedger),
# no en el result backend de Celery. Si algún día se necesita inspeccionar
# resultados de tareas puntuales, usar 'django-db' (backend nativo sobre esta
# misma base, sin infraestructura nueva) — nunca Redis para esto.
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=None)
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = TIME_ZONE
# El pidbox de Celery (control remoto: ping/inspect/broadcast), gossip/mingle
# del worker, y el inspector de Flower declaran colas con
# `transient_nonexcl_queues`, una feature que RabbitMQ 4.x rechaza por defecto
# (error 541). En vez de desactivar remote control (lo que además rompe el
# `inspect` que Flower necesita para listar workers — ver PLAN-DE-MEJORAS.md,
# Bloque #14), se reactiva la feature deprecada a nivel de broker en
# `deploy/rabbitmq.conf` (`deprecated_features.permit.transient_nonexcl_queues`),
# que cubre pidbox/gossip/mingle/Flower a la vez sin apagar ninguno.
CELERY_WORKER_ENABLE_REMOTE_CONTROL = True


# --------------------------------------------------------------------------
# Adaptador BDV — Conciliación (`POST /getMovement/v2`)
# --------------------------------------------------------------------------

# Sin default hardcodeado al host QA real (bdvconciliacionqa.banvenez.com:444,
# investigaciones/research-brief-pagos.md §4.2) — para no arriesgar pegarle
# por accidente sin credenciales explícitas cargadas vía .env.
BDV_CONCILIACION_BASE_URL = env('BDV_CONCILIACION_BASE_URL', default=None)
BDV_CONCILIACION_API_KEY = env('BDV_CONCILIACION_API_KEY', default=None)
BDV_CONCILIACION_TIMEOUT = env.float('BDV_CONCILIACION_TIMEOUT', default=10.0)
