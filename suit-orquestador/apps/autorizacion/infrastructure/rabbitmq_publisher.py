from django.conf import settings
from kombu import Connection, Exchange, Producer

# Exchange topic 'pago' — declarado también por el bootstep consumidor de
# Conciliación (apps/conciliacion/infrastructure/bootsteps.py), con el mismo
# nombre/tipo/durabilidad. La cola ('conciliacion.eventos_pago', routing_key
# 'pago.#') es responsabilidad exclusiva del consumidor: este publisher no la
# declara ni la toca.
PAGO_EXCHANGE = Exchange('pago', type='topic', durable=True)


class PublicacionNoConfirmadaError(Exception):
    """El broker no confirmó la publicación (nack, timeout, o falla de conexión).
    La fila de EventoOutbox debe seguir en pendiente/fallido — nunca marcarse
    enviado ante esta excepción."""


class RabbitMQOutboxPublisher:
    """Publica un EventoOutbox al exchange 'pago' con publisher confirms
    (research-outbox-vs-cdc.md, research-stack-mensajeria.md): la llamada
    bloquea hasta que RabbitMQ confirma la escritura, o lanza excepción — nunca
    se asume publicado sin ese ack explícito del broker."""

    def __init__(self, broker_url=None, exchange=None):
        self._broker_url = broker_url or settings.CELERY_BROKER_URL
        self._exchange = exchange or PAGO_EXCHANGE

    def publicar(self, *, event_id, event_type, payload, schema_version):
        body = {
            'event_id': str(event_id),
            'event_type': event_type,
            'schema_version': schema_version,
            'payload': payload,
        }
        try:
            with Connection(self._broker_url, transport_options={'confirm_publish': True}) as conn:
                channel = conn.channel()
                producer = Producer(channel, exchange=self._exchange)
                producer.publish(
                    body,
                    routing_key=event_type,
                    serializer='json',
                    delivery_mode=2,
                    retry=False,
                )
        except Exception as exc:
            raise PublicacionNoConfirmadaError(str(exc)) from exc
