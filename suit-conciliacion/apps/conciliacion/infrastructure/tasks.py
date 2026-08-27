import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def consumir_evento_pago(evento_data):
    """Punto de entrada del worker Celery que consume directo de la cola RabbitMQ
    `pago.*` (ver config/celery.py::EventoPagoConsumerStep). `evento_data` es el
    envelope publicado por el outbox del Orquestador:
    {event_id, event_type, payload, schema_version}. Entrega *at-least-once*:
    se deduplica por `event_id`, nunca se asume exactly-once."""
    from apps.conciliacion.application.services.ingesta import IngestaService

    evento, creado = IngestaService.registrar_evento(
        event_id=evento_data['event_id'],
        event_type=evento_data['event_type'],
        payload=evento_data['payload'],
        schema_version=evento_data.get('schema_version', 1),
    )

    if not creado and evento.procesado_at is not None:
        logger.info('Evento %s ya procesado, se omite (entrega at-least-once).', evento.event_id)
        return

    # El adaptador HTTP de consulta a BDV (`POST /getMovement/v2`, contrato real
    # en investigaciones/research-brief-pagos.md §4.2) no está implementado
    # todavía — la interpretación de la respuesta ya está lista en
    # MatchingService.procesar_respuesta_bdv() / domain/bdv.py; falta solo el
    # cliente HTTP que arme `respuesta_cruda` (X-API-Key propia de Conciliación,
    # distinta a la del C2P del Orquestador) y el manejo del debounce de 30s
    # del banco. No se fabrica un cliente HTTP sin credenciales/host reales
    # confirmados para este ambiente.
    IngestaService.marcar_procesado(evento)
    logger.info('Evento %s registrado, pendiente de consulta de conciliación al proveedor.', evento.event_id)
