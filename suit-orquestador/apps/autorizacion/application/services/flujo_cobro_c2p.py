from django.db import transaction
from django.utils import timezone

from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import (
    Autorizacion,
    Captura,
    CodigoRespuestaProveedor,
    EventoOutbox,
    IntencionPago,
    MedioPago,
    Moneda,
    ProveedorPago,
    TipoOperacionProveedor,
    TransicionEstadoPago,
    WebhookEntrega,
)

MEDIO_PAGO_CODIGO = 'C2P'
PROVEEDOR_CODIGO = 'BDV'
TIPO_OPERACION_CODIGO = 'CELE'

# investigaciones/contrato-evento-pago-confirmado.md — CERRADO v1, aprobado 2026-08-27.
# Cambiar campos de la v1 en el lugar rompe a Conciliación en silencio: un cambio de
# forma requiere un schema_version nuevo, nunca editar este.
EVENT_TYPE_PAGO_CONFIRMADO = 'pago.confirmado'
SCHEMA_VERSION_PAGO_CONFIRMADO = 1


class FlujoCobroC2PService:
    """Orquesta IntencionPago -> Autorizacion -> Captura para el medio Pago Móvil C2P,
    vía el PaymentProviderPort inyectado (BDVPagoMovilC2PAdapter en producción).

    C2P es cargo instantáneo: process/v2 hace la reserva y el cobro real en una sola
    llamada al banco, por lo que Autorizacion y Captura se crean juntas a partir de la
    misma respuesta exitosa (db-plan-pagos.md 2.5) — no hay una captura separada que
    disparar después. La anulación no se orquesta aquí todavía: queda para el bloque
    que exponga el endpoint público de reversión."""

    @staticmethod
    @transaction.atomic
    def iniciar(*, aplicacion, monto, moneda_codigo, idempotency_key=None):
        moneda = Moneda.objects.get(codigo=moneda_codigo)
        medio_pago = MedioPago.objects.get(codigo=MEDIO_PAGO_CODIGO)
        pago = IntencionPago.objects.create(
            monto=monto, moneda=moneda, medio_pago=medio_pago, aplicacion=aplicacion,
            idempotency_key=idempotency_key,
        )
        TransicionEstadoPago.objects.create(
            pago=pago, estado_anterior=None, estado_nuevo=IntencionPago.EstadoPago.PENDIENTE,
        )
        return pago

    @staticmethod
    def solicitar_otp(*, adaptador, cedula_pagador):
        """No persiste nada propio — la generación de OTP no produce ninguna referencia
        transaccional (db-plan-pagos.md 2.5). El timestamp se registra recién en
        `ejecutar_cobro`, en el `Autorizacion.otp_solicitado_at`."""
        return adaptador.generar_otp(cedula=cedula_pagador)

    @staticmethod
    @transaction.atomic
    def _transicionar(pago, estado_nuevo):
        estado_anterior = pago.estado_actual
        pago.estado_actual = estado_nuevo
        pago.save(update_fields=['estado_actual', 'updated_at'])
        TransicionEstadoPago.objects.create(pago=pago, estado_anterior=estado_anterior, estado_nuevo=estado_nuevo)

    @staticmethod
    def _construir_payload_pago_confirmado(pago, proveedor, captura, cedula_pagador, telefono_pagador, banco_codigo, telefono_comercio):
        fecha_pago = (captura.payload_crudo.get('data') or {}).get('date')
        return {
            'pago_id': str(pago.id),
            'aplicacion_id': str(pago.aplicacion_id),
            'proveedor_codigo': proveedor.codigo,
            'medio_pago_codigo': pago.medio_pago.codigo,
            'monto': str(pago.monto),
            'moneda_codigo': pago.moneda.codigo,
            'cedula_pagador': cedula_pagador,
            'telefono_pagador': telefono_pagador,
            'banco_pagador_codigo': banco_codigo,
            'telefono_comercio': telefono_comercio,
            'referencia_corta': captura.referencia_corta,
            'identificador_interbancario': captura.identificador_interbancario,
            'codigo_respuesta_proveedor': captura.codigo_respuesta.codigo,
            'fecha_pago': fecha_pago,
            'capturado_at': captura.created_at.isoformat(),
            'estado': pago.estado_actual,
            'routing_flag': pago.routing_flag,
            'payload_crudo_captura': captura.payload_crudo,
        }

    @staticmethod
    def ejecutar_cobro(
        pago, *, adaptador, cedula_pagador, telefono_pagador, banco_codigo, concepto, otp, telefono_comercio,
    ):
        proveedor = ProveedorPago.objects.get(codigo=PROVEEDOR_CODIGO)
        tipo_operacion = TipoOperacionProveedor.objects.get(proveedor=proveedor, codigo=TIPO_OPERACION_CODIGO)
        otp_solicitado_at = timezone.now()

        # La llamada al proveedor va fuera de cualquier `atomic()`: es I/O externo, no debe
        # mantener una transacción de Postgres abierta mientras espera la red. Si falla, la
        # transición a `fallido` necesita su propia transacción — si quedara anidada dentro
        # del bloque atómico de éxito, re-lanzar la excepción revertiría también esa transición.
        try:
            resultado = adaptador.procesar_cobro(
                cedula=cedula_pagador,
                telefono_pagador=telefono_pagador,
                monto=pago.monto,
                banco_codigo=banco_codigo,
                concepto=concepto,
                otp=otp,
                moneda_codigo=pago.moneda.codigo,
                tipo_operacion_codigo=TIPO_OPERACION_CODIGO,
                telefono_comercio=telefono_comercio,
            )
        except ProveedorPagoError:
            # Respuesta real del banco (rechazo de negocio): 'fallido' es correcto, es un
            # resultado terminal.
            FlujoCobroC2PService._transicionar(pago, IntencionPago.EstadoPago.FALLIDO)
            raise
        except ProveedorPagoIndisponibleError:
            # Falla de transporte, no una respuesta del banco: el pago nunca llegó a
            # procesarse, así que no es un resultado terminal. Se deja en su estado actual
            # (pendiente, o el mismo estado de un reintento previo) para que un reintento
            # legítimo con la misma idempotency_key pueda volver a llamar a esta misma
            # función sobre el mismo IntencionPago sin violar la máquina de estados.
            raise

        with transaction.atomic():
            codigo_respuesta = CodigoRespuestaProveedor.objects.get(proveedor=proveedor, codigo=resultado.codigo)
            campos_operacion = dict(
                pago=pago,
                proveedor=proveedor,
                tipo_operacion=tipo_operacion,
                codigo_respuesta=codigo_respuesta,
                referencia_proveedor=resultado.identificador_interbancario,
                referencia_corta=resultado.referencia_corta or '',
                identificador_interbancario=resultado.identificador_interbancario or '',
                payload_crudo=resultado.payload_crudo,
                monto=pago.monto,
            )

            autorizacion = Autorizacion.objects.create(**campos_operacion, otp_solicitado_at=otp_solicitado_at)
            FlujoCobroC2PService._transicionar(pago, IntencionPago.EstadoPago.AUTORIZADO)

            captura = Captura.objects.create(**campos_operacion)
            FlujoCobroC2PService._transicionar(pago, IntencionPago.EstadoPago.CAPTURADO)

            # Outbox pattern (db-plan-pagos.md 2.3): mismo transacción que el cambio de
            # estado, nunca publicado directo a RabbitMQ desde acá — un relay separado
            # (no implementado todavía) lee EventoOutbox.estado='pendiente' y publica.
            evento_outbox = EventoOutbox.objects.create(
                pago=pago,
                event_type=EVENT_TYPE_PAGO_CONFIRMADO,
                payload=FlujoCobroC2PService._construir_payload_pago_confirmado(
                    pago, proveedor, captura, cedula_pagador, telefono_pagador, banco_codigo, telefono_comercio,
                ),
                schema_version=SCHEMA_VERSION_PAGO_CONFIRMADO,
            )

            # Webhook server-to-server (Bloque #17 parte 2): solo si la app tiene
            # webhook_url configurada — no toda app lo necesita. Mismo criterio de
            # "escribir en la misma transacción" que el outbox de RabbitMQ: un
            # poller separado (WebhookRelayService) lee estado='pendiente' y entrega.
            if pago.aplicacion.webhook_url:
                WebhookEntrega.objects.create(evento=evento_outbox)

        return autorizacion, captura
