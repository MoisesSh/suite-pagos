import uuid

from apps.autorizacion.application.services import CheckoutTokenService
from apps.autorizacion.domain.models import AplicacionProveedorPermitido, AplicacionRegistrada, DominioPermitido, MedioPago, ProveedorPago
from apps.autorizacion.tests.base import BaseAPITestCase

URL = '/api/autorizacion/cobro/formulario/'


class FormularioCobroViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        DominioPermitido.objects.create(aplicacion=self.aplicacion, dominio='conatel.gob.ve')
        AplicacionProveedorPermitido.objects.create(aplicacion=self.aplicacion, proveedor=self.proveedor)
        self.checkout_token = CheckoutTokenService.generar(
            aplicacion_id=self.aplicacion.id, proveedor_codigo='BDV', monto='1000.60', moneda='VES', concepto='Factura #42',
        )

    def test_token_invalido_responde_403_sin_csp_permisivo(self):
        response = self.client.get(URL, {'checkout_token': 'basura'})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('Content-Security-Policy', response)

    def test_token_valido_sin_origin_ni_referer_responde_200_con_csp_y_parent_origin_null(self):
        response = self.client.get(URL, {'checkout_token': self.checkout_token})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertIn('frame-ancestors', response['Content-Security-Policy'])
        self.assertIn('conatel.gob.ve:*', response['Content-Security-Policy'])
        self.assertIn(b'"parentOrigin": null', response.content)
        # El monto viene del token, no de la URL — no hay ningún query param de monto.
        self.assertIn(b'1000.60', response.content)
        self.assertIn(b'Factura #42', response.content)

    def test_origin_registrado_se_refleja_como_parent_origin(self):
        response = self.client.get(URL, {'checkout_token': self.checkout_token}, HTTP_ORIGIN='https://conatel.gob.ve')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"parentOrigin": "https://conatel.gob.ve"', response.content)

    def test_referer_registrado_como_fallback_cuando_no_hay_origin(self):
        response = self.client.get(
            URL, {'checkout_token': self.checkout_token}, HTTP_REFERER='https://conatel.gob.ve/checkout/pagina',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"parentOrigin": "https://conatel.gob.ve"', response.content)

    def test_origin_no_registrado_responde_403(self):
        response = self.client.get(URL, {'checkout_token': self.checkout_token}, HTTP_ORIGIN='https://phishing-evil.com')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('Content-Security-Policy', response)

    def test_proveedor_no_autorizado_entre_token_y_submit_responde_403(self):
        AplicacionProveedorPermitido.objects.filter(aplicacion=self.aplicacion, proveedor=self.proveedor).update(activo=False)
        response = self.client.get(URL, {'checkout_token': self.checkout_token})
        self.assertEqual(response.status_code, 403)
