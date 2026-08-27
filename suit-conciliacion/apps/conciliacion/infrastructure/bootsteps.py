import logging

from celery import bootsteps
from kombu import Consumer, Exchange, Queue

logger = logging.getLogger(__name__)

pago_exchange = Exchange('pago', type='topic')
# Nombre distinto de `task_default_queue` (config/celery.py) a propósito:
# esta cola solo recibe eventos crudos de dominio (protocolo del outbox de
# Orquestador), nunca mensajes-tarea de Celery. Compartir nombre con la cola
# de tareas causó un loop de reintentos real (ver comentario en celery.py).
pago_queue = Queue('conciliacion.eventos_pago.inbox', exchange=pago_exchange, routing_key='pago.#', durable=True)


class EventoPagoConsumerStep(bootsteps.ConsumerStep):
    """Consume mensajes crudos de RabbitMQ (no son tareas Celery: los publica el
    relay del outbox del Orquestador) y los traduce a la tarea
    `consumir_evento_pago`. Patrón estándar de Celery+RabbitMQ para consumir una
    cola ajena al protocolo de tareas — sin poller custom."""

    def get_consumers(self, channel):
        return [
            Consumer(
                channel,
                queues=[pago_queue],
                callbacks=[self.procesar_mensaje],
                accept=['json'],
            ),
        ]

    def procesar_mensaje(self, body, message):
        from apps.conciliacion.infrastructure.tasks import consumir_evento_pago

        try:
            consumir_evento_pago.delay(body)
        except Exception:
            logger.exception('No se pudo encolar consumir_evento_pago para el mensaje recibido.')
            message.reject(requeue=True)
        else:
            message.ack()
