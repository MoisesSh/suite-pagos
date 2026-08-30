from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.autorizacion.domain.models import WebhookEntrega
from apps.autorizacion.infrastructure.webhook_publisher import WebhookEntregaFallidaError, WebhookPublisher


class WebhookRelayService:
    """Relay del webhook server-to-server (Bloque #17 parte 2 — PLAN-DE-MEJORAS.md):
    mismo patrón que OutboxRelayService (poller Celery beat, SELECT ... FOR UPDATE
    SKIP LOCKED, backoff fijo por tick, sin cálculo exponencial por fila). Tras
    WEBHOOK_MAX_INTENTOS la fila pasa a `agotado` (terminal, requiere revisión
    manual — no hay reintento automático más allá de ese tope)."""

    @staticmethod
    @transaction.atomic
    def procesar_lote(*, limite=None, publisher=None):
        limite = limite or settings.WEBHOOK_RELAY_LOTE_SIZE
        publisher = publisher or WebhookPublisher()
        max_intentos = settings.WEBHOOK_MAX_INTENTOS

        filas = list(
            WebhookEntrega.objects.select_for_update(skip_locked=True)
            .select_related('evento', 'evento__pago__aplicacion')
            .filter(estado=WebhookEntrega.Estado.PENDIENTE)
            .order_by('created_at')[:limite]
        )

        entregados = agotados = reintentados = 0

        for entrega in filas:
            evento = entrega.evento
            aplicacion = evento.pago.aplicacion

            try:
                status_code = publisher.entregar(
                    webhook_url=aplicacion.webhook_url,
                    webhook_secret=aplicacion.webhook_secret,
                    event_id=evento.id,
                    event_type=evento.event_type,
                    payload=evento.payload,
                    schema_version=evento.schema_version,
                )
            except WebhookEntregaFallidaError as exc:
                entrega.intentos += 1
                entrega.ultimo_intento_at = timezone.now()
                entrega.ultima_respuesta_status = exc.status_code
                if entrega.intentos >= max_intentos:
                    entrega.estado = WebhookEntrega.Estado.AGOTADO
                    agotados += 1
                else:
                    reintentados += 1
                entrega.save(update_fields=['intentos', 'ultimo_intento_at', 'ultima_respuesta_status', 'estado'])
                continue

            entrega.intentos += 1
            entrega.ultimo_intento_at = timezone.now()
            entrega.ultima_respuesta_status = status_code
            entrega.estado = WebhookEntrega.Estado.ENTREGADO
            entrega.save(update_fields=['intentos', 'ultimo_intento_at', 'ultima_respuesta_status', 'estado'])
            entregados += 1

        return {'entregados': entregados, 'agotados': agotados, 'reintentados': reintentados}
