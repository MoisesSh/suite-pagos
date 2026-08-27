from decimal import Decimal

from django.conf import settings
from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.autorizacion.api.checkout_token_resolver import resolver_checkout_token
from apps.autorizacion.api.serializers import (
    EjecutarCobroRequestSerializer,
    SolicitarOtpRequestSerializer,
    ValidarAccesoRequestSerializer,
)
from apps.autorizacion.application.services import (
    AccesoNoAutorizadoError,
    CheckoutTokenService,
    FlujoCobroC2PService,
    IdempotencyConflictError,
    IdempotencyService,
    ValidacionAccesoService,
)
from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import CodigoRespuestaProveedor, IdempotencyKey, ProveedorPago
from apps.autorizacion.infrastructure.adapters.bdv_c2p import BDVPagoMovilC2PAdapter

# Mapeo de categoría de CodigoRespuestaProveedor -> status HTTP de la respuesta pública.
# duplicado_idempotente -> 409 (el banco ya vio esta operación, mismo criterio que nuestra
# propia idempotencia). error_negocio -> 402 (pago rechazado por un motivo del pagador/cuenta,
# no un fallo del sistema). error_tecnico -> 503 (falla del lado del proveedor/conector).
_STATUS_POR_CATEGORIA = {
    CodigoRespuestaProveedor.Categoria.DUPLICADO_IDEMPOTENTE: status.HTTP_409_CONFLICT,
    CodigoRespuestaProveedor.Categoria.ERROR_NEGOCIO: status.HTTP_402_PAYMENT_REQUIRED,
    CodigoRespuestaProveedor.Categoria.ERROR_TECNICO: status.HTTP_503_SERVICE_UNAVAILABLE,
}


class ValidarAccesoView(views.APIView):
    """Control de seguridad bloqueante (db-plan-pagos.md 2.0): valida
    dominio -> aplicación -> proveedor autorizado. No crea ninguna
    IntencionPago. Si autoriza, emite un checkout_token (CheckoutTokenService)
    que los endpoints de cobro exigen en vez de re-derivar el dominio del
    Origin/Referer en cada submit (research-seguridad-iframe.md sección 3)."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ValidarAccesoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            aplicacion = ValidacionAccesoService.validar(
                dominio=serializer.validated_data['dominio'],
                proveedor_codigo=serializer.validated_data['proveedor'],
            )
        except AccesoNoAutorizadoError as exc:
            return Response({'autorizado': False, 'motivo': exc.motivo}, status=status.HTTP_403_FORBIDDEN)

        checkout_token = CheckoutTokenService.generar(
            aplicacion_id=aplicacion.id,
            proveedor_codigo=serializer.validated_data['proveedor'],
            monto=serializer.validated_data['monto'],
            moneda=serializer.validated_data['moneda'],
            concepto=serializer.validated_data['concepto'],
        )
        return Response(
            {'autorizado': True, 'aplicacion': aplicacion.nombre, 'checkout_token': checkout_token},
            status=status.HTTP_200_OK,
        )


class SolicitarOtpView(views.APIView):
    """Dispara el envío de la clave OTP al pagador (paso 1 del flujo C2P). No crea
    ninguna IntencionPago ni usa idempotencia — repetirlo solo reenvía el OTP,
    mitigado por throttling, no por deduplicación de cobro."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'cobro_c2p_otp'

    def post(self, request):
        serializer = SolicitarOtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        _aplicacion, _payload, error_response = resolver_checkout_token(datos['checkout_token'], datos['proveedor'])
        if error_response is not None:
            return error_response

        adaptador = BDVPagoMovilC2PAdapter()
        try:
            FlujoCobroC2PService.solicitar_otp(adaptador=adaptador, cedula_pagador=datos['cedula_pagador'])
        except ProveedorPagoError as exc:
            return Response(
                {'error': 'proveedor_rechazo_otp', 'codigo_proveedor': exc.codigo}, status=status.HTTP_400_BAD_REQUEST,
            )
        except ProveedorPagoIndisponibleError:
            return Response({'error': 'proveedor_no_disponible'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({'resultado': 'otp_enviado'}, status=status.HTTP_200_OK)


class EjecutarCobroView(views.APIView):
    """Endpoint público de cobro (paso 2+3 del flujo C2P, unificados: BDV cobra en una
    sola llamada). Crea IntencionPago -> Autorizacion -> Captura vía FlujoCobroC2PService.
    Deduplicado por idempotency_key (db-plan-pagos.md 2.3): un reintento con la misma key
    y el mismo payload canónico devuelve la respuesta ya resuelta en vez de volver a
    cobrar; con un payload distinto, se rechaza."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'cobro_c2p'

    def post(self, request):
        serializer = EjecutarCobroRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        aplicacion, token_payload, error_response = resolver_checkout_token(
            datos['checkout_token'], datos['proveedor'],
        )
        if error_response is not None:
            return error_response

        # monto/moneda/concepto vienen del token verificado, nunca del body del
        # submit — ver el docstring de EjecutarCobroRequestSerializer.
        monto = Decimal(token_payload['monto'])
        moneda = token_payload['moneda']
        concepto = token_payload.get('concepto', 'Pago')

        payload_canonico = {
            'proveedor': datos['proveedor'],
            'monto': str(monto),
            'moneda': moneda,
            'cedula_pagador': datos['cedula_pagador'],
            'telefono_pagador': datos['telefono_pagador'],
            'banco_codigo': datos['banco_codigo'],
        }
        try:
            idem, creada = IdempotencyService.obtener_o_crear(datos['idempotency_key'], payload_canonico)
        except IdempotencyConflictError:
            return Response({'error': 'idempotency_key_conflicto'}, status=status.HTTP_409_CONFLICT)

        if not creada and idem.estado in (IdempotencyKey.Estado.COMPLETADO, IdempotencyKey.Estado.RECHAZADO):
            snapshot = idem.response_snapshot or {}
            return Response(snapshot.get('body', {}), status=snapshot.get('status_code', status.HTTP_200_OK))

        # idem.estado == PENDIENTE aquí: primera vez (creada=True), o un reintento legítimo
        # de un intento anterior que no llegó a completarse (timeout/caída de red). En ese
        # segundo caso reusamos el IntencionPago ya creado en vez de crear uno nuevo — el
        # OneToOneField IdempotencyKey.intencion_pago no admite una segunda fila.
        pago = getattr(idem, 'intencion_pago', None)
        if pago is None:
            pago = FlujoCobroC2PService.iniciar(
                aplicacion=aplicacion, monto=monto, moneda_codigo=moneda, idempotency_key=idem,
            )

        adaptador = BDVPagoMovilC2PAdapter()
        try:
            _autorizacion, captura = FlujoCobroC2PService.ejecutar_cobro(
                pago, adaptador=adaptador,
                cedula_pagador=datos['cedula_pagador'], telefono_pagador=datos['telefono_pagador'],
                banco_codigo=datos['banco_codigo'], concepto=concepto, otp=datos['otp'],
                telefono_comercio=settings.BDV_C2P_TELEFONO_COMERCIO,
            )
        except ProveedorPagoError as exc:
            proveedor = ProveedorPago.objects.get(codigo=datos['proveedor'])
            categoria = CodigoRespuestaProveedor.objects.filter(proveedor=proveedor, codigo=exc.codigo).values_list(
                'categoria', flat=True,
            ).first()
            status_code = _STATUS_POR_CATEGORIA.get(categoria, status.HTTP_402_PAYMENT_REQUIRED)
            body = {'error': 'proveedor_rechazo_cobro', 'codigo_proveedor': exc.codigo, 'pago_id': str(pago.id)}
            IdempotencyService.finalizar(idem, estado=IdempotencyKey.Estado.RECHAZADO, status_code=status_code, body=body)
            return Response(body, status=status_code)
        except ProveedorPagoIndisponibleError:
            # Falla de transporte, no de negocio: no se marca completado/rechazado — la
            # idempotency key queda pendiente para que un reintento legítimo la reuse.
            return Response(
                {'error': 'proveedor_no_disponible', 'pago_id': str(pago.id)}, status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        body = {'pago_id': str(pago.id), 'estado': pago.estado_actual, 'referencia_corta': captura.referencia_corta}
        IdempotencyService.finalizar(idem, estado=IdempotencyKey.Estado.COMPLETADO, status_code=status.HTTP_200_OK, body=body)
        return Response(body, status=status.HTTP_200_OK)
