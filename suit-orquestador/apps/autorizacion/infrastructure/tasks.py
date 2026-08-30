import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def publicar_eventos_outbox():
    """Dispara OutboxRelayService.procesar_lote() — registrada en el beat_schedule
    de config/celery.py cada OUTBOX_RELAY_INTERVALO_SEGUNDOS. Sin autoretry propio:
    cada fila ya maneja su propio reintento/backoff a nivel de EventoOutbox.intentos,
    reintentar la task entera duplicaría esa lógica."""
    from apps.autorizacion.application.services.outbox_relay import OutboxRelayService

    resultado = OutboxRelayService.procesar_lote()
    if resultado['enviados'] or resultado['fallidos']:
        logger.info(
            'Relay de outbox: %s enviados, %s reintentados, %s fallidos definitivamente.',
            resultado['enviados'], resultado['reintentados'], resultado['fallidos'],
        )
    return resultado


@shared_task
def entregar_webhooks():
    """Dispara WebhookRelayService.procesar_lote() — registrada en el
    beat_schedule de config/celery.py cada WEBHOOK_RELAY_INTERVALO_SEGUNDOS.
    Sin autoretry propio: cada fila ya maneja su propio reintento/backoff a
    nivel de WebhookEntrega.intentos (Bloque #17 parte 2)."""
    from apps.autorizacion.application.services.webhook_relay import WebhookRelayService

    resultado = WebhookRelayService.procesar_lote()
    if resultado['entregados'] or resultado['agotados']:
        logger.info(
            'Relay de webhooks: %s entregados, %s reintentados, %s agotados definitivamente.',
            resultado['entregados'], resultado['reintentados'], resultado['agotados'],
        )
    return resultado
