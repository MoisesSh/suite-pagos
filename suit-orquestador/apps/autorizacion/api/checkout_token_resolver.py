from rest_framework import status
from rest_framework.response import Response

from apps.autorizacion.application.services import (
    AccesoNoAutorizadoError,
    CheckoutTokenInvalidoError,
    CheckoutTokenService,
    ValidacionAccesoService,
)


def resolver_checkout_token(checkout_token, proveedor_codigo):
    """Común a los endpoints JSON de cobro y a la vista HTML del formulario
    embebido: valida la firma/vigencia del token, que el proveedor solicitado
    coincida con el autorizado en el token, y re-valida app/proveedor por si la
    autorización cambió entre la emisión del token y este submit (el token puede
    vivir hasta CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS). Devuelve (aplicacion, payload,
    None) o (None, None, Response) con el error ya armado. `payload` trae
    monto/moneda/concepto atados al token — es la fuente de verdad para /cobro/,
    nunca el body del submit ni un query param editable."""
    try:
        payload = CheckoutTokenService.verificar(checkout_token)
    except CheckoutTokenInvalidoError:
        return None, None, Response({'error': 'checkout_token_invalido'}, status=status.HTTP_401_UNAUTHORIZED)

    if payload['proveedor_codigo'] != proveedor_codigo:
        return None, None, Response({'error': 'proveedor_no_coincide_con_token'}, status=status.HTTP_403_FORBIDDEN)

    try:
        aplicacion = ValidacionAccesoService.validar_por_aplicacion(
            aplicacion_id=payload['aplicacion_id'], proveedor_codigo=proveedor_codigo,
        )
    except AccesoNoAutorizadoError as exc:
        return None, None, Response({'error': exc.motivo}, status=status.HTTP_403_FORBIDDEN)

    return aplicacion, payload, None
