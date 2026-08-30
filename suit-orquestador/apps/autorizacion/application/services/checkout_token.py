import hashlib

from django.conf import settings
from django.core import signing
from django.db import IntegrityError

SALT = 'autorizacion.checkout_token'


class CheckoutTokenInvalidoError(Exception):
    """Token vencido o manipulado — el endpoint de cobro debe devolver 401 genérico,
    nunca el detalle interno de la firma."""


class CheckoutTokenYaUtilizadoError(Exception):
    """El token ya se usó para completar un cobro — no depende de que el cliente
    reuse la misma idempotency_key (esa la genera el propio cliente, un UUID
    nuevo por intento no está atado al checkout_token)."""


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
            key=settings.CHECKOUT_TOKEN_SIGNING_KEY,
        )

    @staticmethod
    def verificar(token):
        try:
            return signing.loads(
                token, salt=SALT, max_age=settings.CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS,
                key=settings.CHECKOUT_TOKEN_SIGNING_KEY,
            )
        except signing.BadSignature as exc:
            raise CheckoutTokenInvalidoError('token_invalido_o_expirado') from exc

    @staticmethod
    def hash_de(token):
        # No se guarda el token firmado tal cual (viaja monto/moneda/concepto
        # legibles, ver reporte-seguridad-y-precio-iframe.md #1: signing.dumps
        # firma, no cifra) — solo su hash, como identificador de uso único.
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def esta_consumido(token):
        from apps.autorizacion.domain.models import CheckoutTokenConsumido

        return CheckoutTokenConsumido.objects.filter(token_hash=CheckoutTokenService.hash_de(token)).exists()

    @staticmethod
    def marcar_consumido(token, pago):
        from apps.autorizacion.domain.models import CheckoutTokenConsumido

        try:
            CheckoutTokenConsumido.objects.create(token_hash=CheckoutTokenService.hash_de(token), pago=pago)
        except IntegrityError:
            # Carrera entre dos requests concurrentes con el mismo token: la
            # segunda en llegar a este punto pierde la carrera de la constraint
            # unique — no es un error real, el token ya quedó marcado.
            raise CheckoutTokenYaUtilizadoError('checkout_token_ya_utilizado')
