import logging
from decimal import Decimal

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def consumir_evento_pago(evento_data):
    """Punto de entrada del worker Celery que consume directo de la cola RabbitMQ
    `pago.*` (ver config/celery.py::EventoPagoConsumerStep). `evento_data` es el
    envelope publicado por el outbox del Orquestador:
    {event_id, event_type, payload, schema_version}. Entrega *at-least-once*:
    se deduplica por `event_id`, nunca se asume exactly-once.

    Contrato de `payload` para `event_type == 'pago.confirmado'`:
    investigaciones/contrato-evento-pago-confirmado.md (v1, CERRADO). El relay
    Orquestador→RabbitMQ que publica esto todavía no existe del lado
    suit-orquestador (punto abierto #2 del plan) — esta task ya está lista
    para cuando exista."""
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

    if evento.event_type == 'pago.confirmado':
        _procesar_pago_confirmado(evento)

    IngestaService.marcar_procesado(evento)


def _procesar_pago_confirmado(evento):
    from apps.conciliacion.application.services.matching import MatchingService
    from apps.conciliacion.domain.models import Banco, Discrepancia
    from apps.conciliacion.infrastructure.bdv_conciliacion_client import BdvConciliacionClient

    payload = evento.payload

    try:
        banco = Banco.objects.get(codigo=payload['banco_pagador_codigo'])
    except Banco.DoesNotExist:
        logger.error(
            'Banco %s no está en el catálogo local de Conciliación — evento %s queda en revisión manual.',
            payload['banco_pagador_codigo'], evento.event_id,
        )
        Discrepancia.objects.create(
            evento=evento,
            tipo=Discrepancia.Tipo.ERROR_PROVEEDOR,
            severidad=Discrepancia.Severidad.CRITICA,
            notas=f"Banco {payload['banco_pagador_codigo']} no está en el catálogo local (Banco) de Conciliación.",
        )
        return

    respuesta_cruda = BdvConciliacionClient().consultar_movimiento(
        cedula_pagador=payload['cedula_pagador'],
        telefono_pagador=payload['telefono_pagador'],
        telefono_destino=payload['telefono_comercio'],
        referencia_corta=payload['referencia_corta'],
        fecha_pago=payload['fecha_pago'],
        importe=payload['monto'],
        banco_origen_codigo=payload['banco_pagador_codigo'],
    )

    MatchingService.procesar_respuesta_bdv(
        evento=evento,
        banco=banco,
        referencia_corta=payload['referencia_corta'],
        telefono_pagador=payload['telefono_pagador'],
        cedula_pagador=payload['cedula_pagador'],
        importe_esperado=Decimal(payload['monto']),
        fecha_pago=payload['fecha_pago'],
        respuesta_cruda=respuesta_cruda,
    )
