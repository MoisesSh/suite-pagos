import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('suit_orquestador')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['apps.autorizacion'], related_name='infrastructure.tasks')

# Relay del outbox (research-outbox-vs-cdc.md): poller Celery beat sobre EventoOutbox,
# no CDC/Debezium. El intervalo es configurable por env, no crítico (la latencia
# objetivo de Conciliación es de minutos, no segundos).
app.conf.beat_schedule = {
    'publicar-eventos-outbox': {
        'task': 'apps.autorizacion.infrastructure.tasks.publicar_eventos_outbox',
        'schedule': float(os.environ.get('OUTBOX_RELAY_INTERVALO_SEGUNDOS', '5')),
    },
}
