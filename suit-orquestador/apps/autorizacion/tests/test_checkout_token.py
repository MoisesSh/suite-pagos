import uuid

from django.test import override_settings

from apps.autorizacion.application.services import CheckoutTokenInvalidoError, CheckoutTokenService
from apps.autorizacion.tests.base import BaseAPITestCase


class CheckoutTokenServiceTests(BaseAPITestCase):
    def test_generar_y_verificar_roundtrip(self):
        aplicacion_id = uuid.uuid4()
        token = CheckoutTokenService.generar(aplicacion_id=aplicacion_id, proveedor_codigo='BDV')

        payload = CheckoutTokenService.verificar(token)

        self.assertEqual(payload['aplicacion_id'], str(aplicacion_id))
        self.assertEqual(payload['proveedor_codigo'], 'BDV')

    def test_token_manipulado_lanza_invalido(self):
        token = CheckoutTokenService.generar(aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV')
        token_manipulado = token[:-1] + ('a' if token[-1] != 'a' else 'b')

        with self.assertRaises(CheckoutTokenInvalidoError):
            CheckoutTokenService.verificar(token_manipulado)

    @override_settings(CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS=-1)
    def test_token_vencido_lanza_invalido(self):
        # -1 en vez de 0: con max_age=0 la edad medida en el mismo segundo puede dar
        # exactamente 0 y no superar el umbral (0 > 0 es False) — no dispara la excepción
        # de forma confiable. -1 garantiza el vencimiento sin depender de timing.
        token = CheckoutTokenService.generar(aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV')

        with self.assertRaises(CheckoutTokenInvalidoError):
            CheckoutTokenService.verificar(token)
