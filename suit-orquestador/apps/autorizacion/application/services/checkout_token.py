from django.conf import settings
from django.core import signing

SALT = 'autorizacion.checkout_token'


class CheckoutTokenInvalidoError(Exception):
    """Token vencido o manipulado — el endpoint de cobro debe devolver 401 genérico,
    nunca el detalle interno de la firma."""


class CheckoutTokenService:
    """Token de sesión de checkout emitido por ValidarAccesoView tras validar
    dominio -> aplicación -> proveedor (research-seguridad-iframe.md sección 3):
    el Origin/Referer del POST que ejecuta el cobro, hecho desde JS corriendo
    dentro del iframe, refleja el origen del propio formulario del Orquestador,
    no el de la app consumidora que lo embebe — por eso esa identidad no puede
    re-derivarse del header en cada submit. Se captura una sola vez en la
    validación inicial y viaja firmada en este token."""

    @staticmethod
    def generar(*, aplicacion_id, proveedor_codigo):
        return signing.dumps(
            {'aplicacion_id': str(aplicacion_id), 'proveedor_codigo': proveedor_codigo}, salt=SALT,
        )

    @staticmethod
    def verificar(token):
        try:
            return signing.loads(token, salt=SALT, max_age=settings.CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS)
        except signing.BadSignature as exc:
            raise CheckoutTokenInvalidoError('token_invalido_o_expirado') from exc
