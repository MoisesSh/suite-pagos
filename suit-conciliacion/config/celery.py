import os

from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('suit_conciliacion')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Cola dedicada, atada al exchange topic `pago` del Orquestador — consumo
# directo de RabbitMQ (patrón estándar Celery+RabbitMQ), sin poller propio.
# El poller de EventoOutbox (research-outbox-vs-cdc.md) es exclusivo del
# lado Orquestador para su propia tabla, no aplica a Conciliación.
pago_exchange = Exchange('pago', type='topic')
app.conf.task_queues = (
    Queue('conciliacion.eventos_pago', exchange=pago_exchange, routing_key='pago.#', durable=True),
)
app.conf.task_default_queue = 'conciliacion.eventos_pago'

app.autodiscover_tasks(['apps.conciliacion'], related_name='infrastructure.tasks')

# Bootstep que consume los mensajes crudos de `pago.*` (no son tareas Celery
# nativas: los publica el relay del outbox del Orquestador) y los traduce a
# la tarea `consumir_evento_pago`.
from apps.conciliacion.infrastructure.bootsteps import EventoPagoConsumerStep  # noqa: E402

app.steps['consumer'].add(EventoPagoConsumerStep)
