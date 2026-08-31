from django.db import transaction
from django.utils import timezone

from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import (
    Anulacion,
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

# Mismo criterio que pago.confirmado (Bloque #22): forma cerrada desde su primera
# versión, un cambio de campos exige subir schema_version, nunca editar la v1.
EVENT_TYPE_PAGO_ANULADO = 'pago.anulado'
SCHEMA_VERSION_PAGO_ANULADO = 1


class PagoNoAnulableError(Exception):
    """Solo un IntencionPago en estado CAPTURADO tiene un identificador_interbancario
    real que BDV pueda anular — no hay nada que revertir en otro estado."""

    def __init__(self, estado_actual):
        self.estado_actual = estado_actual
        super().__init__(f'IntencionPago en estado {estado_actual!r} no es anulable')


class FlujoCobroC2PService:
    """Orquesta IntencionPago -> Autorizacion -> Captura para el medio Pago Móvil C2P,
    vía el PaymentProviderPort inyectado (BDVPagoMovilC2PAdapter en producción).

    C2P es cargo instantáneo: process/v2 hace la reserva y el cobro real en una sola
    llamada al banco, por lo que Autorizacion y Captura se crean juntas a partir de la
    misma respuesta exitosa (db-plan-pagos.md 2.5) — no hay una captura separada que
    disparar después. La anulación (Bloque #22) solo la dispara staff de Conatel desde
    suit-panel, sin endpoint público equivalente ni ventana de tiempo propia: se
    intenta siempre contra BDV y, si el banco la rechaza por su propia ventana, ese
    rechazo se propaga tal cual."""

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

    @staticmethod
    def _construir_payload_pago_anulado(pago, proveedor, anulacion):
        return {
            'pago_id': str(pago.id),
            'aplicacion_id': str(pago.aplicacion_id),
            'proveedor_codigo': proveedor.codigo,
            'medio_pago_codigo': pago.medio_pago.codigo,
            'monto': str(pago.monto),
            'moneda_codigo': pago.moneda.codigo,
            'referencia_corta': anulacion.referencia_corta,
            'identificador_interbancario': anulacion.identificador_interbancario,
            'codigo_respuesta_proveedor': anulacion.codigo_respuesta.codigo,
            'anulado_at': anulacion.created_at.isoformat(),
            'estado': pago.estado_actual,
            'payload_crudo_anulacion': anulacion.payload_crudo,
        }

    @staticmethod
    def anular_cobro(pago, *, adaptador, referencia_origen=None):
        """Revierte un cobro ya capturado. Sin ventana de tiempo propia (decisión de
        negocio, Bloque #22): siempre se intenta contra BDV, y si el banco rechaza por
        su propia ventana de anulación (u otro motivo de negocio), ese ProveedorPagoError
        se propaga tal cual — no se atrapa ni se traduce acá."""
        if pago.estado_actual != IntencionPago.EstadoPago.CAPTURADO:
            raise PagoNoAnulableError(pago.estado_actual)

        captura = pago.capturas.latest('created_at')
        proveedor = ProveedorPago.objects.get(codigo=PROVEEDOR_CODIGO)
        tipo_operacion = TipoOperacionProveedor.objects.get(proveedor=proveedor, codigo=TIPO_OPERACION_CODIGO)

        # I/O externo fuera de atomic(), mismo criterio que ejecutar_cobro. Ni
        # ProveedorPagoError ni ProveedorPagoIndisponibleError se atrapan acá: en
        # ambos casos el pago se queda en CAPTURADO tal cual estaba, sin persistir
        # ninguna Anulacion — no hubo reversión real que registrar.
        resultado = adaptador.anular(
            identificador_interbancario=captura.identificador_interbancario,
            referencia_origen=referencia_origen,
        )

        with transaction.atomic():
            codigo_respuesta = CodigoRespuestaProveedor.objects.get(proveedor=proveedor, codigo=resultado.codigo)
            anulacion = Anulacion.objects.create(
                pago=pago,
                proveedor=proveedor,
                tipo_operacion=tipo_operacion,
                codigo_respuesta=codigo_respuesta,
                referencia_proveedor=captura.identificador_interbancario,
                referencia_corta=captura.referencia_corta,
                identificador_interbancario=captura.identificador_interbancario,
                payload_crudo=resultado.payload_crudo,
                monto=pago.monto,
            )
            FlujoCobroC2PService._transicionar(pago, IntencionPago.EstadoPago.ANULADO)

            # Mismo outbox pattern que pago.confirmado: sin este evento, Conciliación
            # nunca se entera de la reversión y el ledger queda con un cobro fantasma
            # que ya nadie va a conciliar.
            EventoOutbox.objects.create(
                pago=pago,
                event_type=EVENT_TYPE_PAGO_ANULADO,
                payload=FlujoCobroC2PService._construir_payload_pago_anulado(pago, proveedor, anulacion),
                schema_version=SCHEMA_VERSION_PAGO_ANULADO,
            )

        return anulacion
