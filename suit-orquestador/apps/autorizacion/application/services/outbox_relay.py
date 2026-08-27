from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.autorizacion.domain.models import EventoOutbox
from apps.autorizacion.infrastructure.rabbitmq_publisher import PublicacionNoConfirmadaError, RabbitMQOutboxPublisher


class OutboxRelayService:
    """Relay del outbox pattern (research-outbox-vs-cdc.md): poller Celery beat,
    no CDC/Debezium. Backoff fijo por el propio intervalo del tick del beat, sin
    cálculo de backoff exponencial por fila — no se justifica al volumen de este
    MVP (piloto 5-10%); tras OUTBOX_RELAY_MAX_INTENTOS la fila pasa a `fallido`
    (terminal, requiere revisión manual, nunca se reintenta sola de nuevo)."""

    @staticmethod
    @transaction.atomic
    def procesar_lote(*, limite=None, publisher=None):
        limite = limite or settings.OUTBOX_RELAY_LOTE_SIZE
        publisher = publisher or RabbitMQOutboxPublisher()
        max_intentos = settings.OUTBOX_RELAY_MAX_INTENTOS

        # FOR UPDATE SKIP LOCKED: permite correr varios workers del relay en
        # paralelo sin que se pisen sobre las mismas filas (research-outbox-vs-cdc.md
        # sección 5). Los locks se mantienen por la duración del lote, incluyendo
        # la publicación — es el mismo patrón descrito ahí, no una optimización propia.
        filas = list(
            EventoOutbox.objects.select_for_update(skip_locked=True)
            .filter(estado=EventoOutbox.Estado.PENDIENTE)
            .order_by('created_at')[:limite]
        )

        enviados = fallidos = reintentados = 0

        for evento in filas:
            try:
                publisher.publicar(
                    event_id=evento.id,
                    event_type=evento.event_type,
                    payload=evento.payload,
                    schema_version=evento.schema_version,
                )
            except PublicacionNoConfirmadaError:
                evento.intentos += 1
                evento.ultimo_intento_at = timezone.now()
                if evento.intentos >= max_intentos:
                    evento.estado = EventoOutbox.Estado.FALLIDO
                    fallidos += 1
                else:
                    reintentados += 1
                evento.save(update_fields=['intentos', 'ultimo_intento_at', 'estado'])
                continue

            # Solo se marca enviado tras el confirm explícito del broker (ver
            # RabbitMQOutboxPublisher) — nunca antes.
            evento.estado = EventoOutbox.Estado.ENVIADO
            evento.sent_at = timezone.now()
            evento.save(update_fields=['estado', 'sent_at'])
            enviados += 1

        return {'enviados': enviados, 'fallidos': fallidos, 'reintentados': reintentados}
