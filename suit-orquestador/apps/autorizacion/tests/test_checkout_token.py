import uuid

from django.conf import settings
from django.core import signing
from django.test import override_settings

from apps.autorizacion.application.services import CheckoutTokenInvalidoError, CheckoutTokenService
from apps.autorizacion.domain.models import AplicacionRegistrada
from apps.autorizacion.tests.base import BaseAPITestCase


class CheckoutTokenServiceTests(BaseAPITestCase):
    def test_generar_y_verificar_roundtrip(self):
        aplicacion_id = uuid.uuid4()
        token = CheckoutTokenService.generar(
            aplicacion_id=aplicacion_id, proveedor_codigo='BDV', monto='1000.60', moneda='VES', concepto='Pago prueba',
        )

        payload = CheckoutTokenService.verificar(token)

        self.assertEqual(payload['aplicacion_id'], str(aplicacion_id))
        self.assertEqual(payload['proveedor_codigo'], 'BDV')
        self.assertEqual(payload['monto'], '1000.60')
        self.assertEqual(payload['moneda'], 'VES')
        self.assertEqual(payload['concepto'], 'Pago prueba')

    def test_generar_sin_concepto_usa_default_pago(self):
        token = CheckoutTokenService.generar(aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV', monto='10.00', moneda='VES')
        payload = CheckoutTokenService.verificar(token)
        self.assertEqual(payload['concepto'], 'Pago')

    def test_token_manipulado_lanza_invalido(self):
        token = CheckoutTokenService.generar(
            aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV', monto='1000.60', moneda='VES',
        )
        token_manipulado = token[:-1] + ('a' if token[-1] != 'a' else 'b')

        with self.assertRaises(CheckoutTokenInvalidoError):
            CheckoutTokenService.verificar(token_manipulado)

    @override_settings(CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS=-1)
    def test_token_vencido_lanza_invalido(self):
        # -1 en vez de 0: con max_age=0 la edad medida en el mismo segundo puede dar
        # exactamente 0 y no superar el umbral (0 > 0 es False) — no dispara la excepción
        # de forma confiable. -1 garantiza el vencimiento sin depender de timing.
        token = CheckoutTokenService.generar(
            aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV', monto='1000.60', moneda='VES',
        )

        with self.assertRaises(CheckoutTokenInvalidoError):
            CheckoutTokenService.verificar(token)

    def test_firma_es_independiente_de_secret_key(self):
        """Hallazgo de seguridad: antes signing.dumps/loads no pasaba `key=`, así
        que firmaba con SECRET_KEY (la misma que sesiones/CSRF de Django). Un
        token real debe fallar si se intenta verificar con SECRET_KEY en vez de
        CHECKOUT_TOKEN_SIGNING_KEY — prueba que ya no comparten clave."""
        token = CheckoutTokenService.generar(
            aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV', monto='1000.60', moneda='VES',
        )
        with self.assertRaises(signing.BadSignature):
            signing.loads(token, salt='autorizacion.checkout_token', key=settings.SECRET_KEY)
        # Con la clave correcta sí valida.
        CheckoutTokenService.verificar(token)

    def test_hash_de_token_es_estable_y_distinto_por_token(self):
        token1 = CheckoutTokenService.generar(aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV', monto='1.00', moneda='VES')
        token2 = CheckoutTokenService.generar(aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV', monto='1.00', moneda='VES')
        self.assertEqual(CheckoutTokenService.hash_de(token1), CheckoutTokenService.hash_de(token1))
        self.assertNotEqual(CheckoutTokenService.hash_de(token1), CheckoutTokenService.hash_de(token2))

    def test_marcar_consumido_y_esta_consumido(self):
        aplicacion = AplicacionRegistrada.objects.create(nombre='Test', app_origen_id=uuid.uuid4())
        from apps.autorizacion.application.services import FlujoCobroC2PService
        from decimal import Decimal

        pago = FlujoCobroC2PService.iniciar(aplicacion=aplicacion, monto=Decimal('10.00'), moneda_codigo='VES')
        token = CheckoutTokenService.generar(aplicacion_id=aplicacion.id, proveedor_codigo='BDV', monto='10.00', moneda='VES')

        self.assertFalse(CheckoutTokenService.esta_consumido(token))
        CheckoutTokenService.marcar_consumido(token, pago)
        self.assertTrue(CheckoutTokenService.esta_consumido(token))

    def test_marcar_consumido_dos_veces_lanza_ya_utilizado(self):
        from apps.autorizacion.application.services import CheckoutTokenYaUtilizadoError, FlujoCobroC2PService
        from decimal import Decimal

        aplicacion = AplicacionRegistrada.objects.create(nombre='Test', app_origen_id=uuid.uuid4())
        pago = FlujoCobroC2PService.iniciar(aplicacion=aplicacion, monto=Decimal('10.00'), moneda_codigo='VES')
        token = CheckoutTokenService.generar(aplicacion_id=aplicacion.id, proveedor_codigo='BDV', monto='10.00', moneda='VES')

        CheckoutTokenService.marcar_consumido(token, pago)
        with self.assertRaises(CheckoutTokenYaUtilizadoError):
            CheckoutTokenService.marcar_consumido(token, pago)
