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
    validación inicial y viaja firmada en este token.

    `monto`/`moneda`/`concepto` viajan atados criptográficamente acá, no en el
    body del submit de /cobro/: el OTP autentica al pagador, no valida que el
    monto sea el que la app realmente factura — sin esto, un pagador técnico
    podría editar el monto en el request de cobro y bajarse su propia factura.
    La app consumidora los declara al iniciar el checkout (ValidarAccesoView),
    momento en el que ya sabe cuánto está facturando."""

    @staticmethod
    def generar(*, aplicacion_id, proveedor_codigo, monto, moneda, concepto='Pago'):
        return signing.dumps(
            {
                'aplicacion_id': str(aplicacion_id),
                'proveedor_codigo': proveedor_codigo,
                'monto': str(monto),
                'moneda': moneda,
                'concepto': concepto,
            },
            salt=SALT,
        )

    @staticmethod
    def verificar(token):
        try:
            return signing.loads(token, salt=SALT, max_age=settings.CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS)
        except signing.BadSignature as exc:
            raise CheckoutTokenInvalidoError('token_invalido_o_expirado') from exc
