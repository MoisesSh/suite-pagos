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
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
if DEBUG and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOW_ALL_ORIGINS = True  # solo en desarrollo sin configurar
CORS_ALLOW_CREDENTIALS = True  # el refresh token viaja en cookie HttpOnly

# Origen fijo del Developer Portal (suit-portal), permitido a embeber
# /api/docs/ y /api/schema/ por iframe (ver config/urls.py). Documentación
# interna, no un flujo de pago crítico (a diferencia del formulario de cobro
# del Orquestador) — alcanza con un origen fijo por env var, sin catálogo
# dinámico de dominios ni token firmado.
PORTAL_ORIGIN = env('PORTAL_ORIGIN', default='http://localhost:3001')


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

DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
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
