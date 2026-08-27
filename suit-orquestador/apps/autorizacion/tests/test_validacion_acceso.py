import uuid

from apps.autorizacion.application.services import AccesoNoAutorizadoError, ValidacionAccesoService
from apps.autorizacion.domain.models import (
    AplicacionProveedorPermitido,
    AplicacionRegistrada,
    DominioPermitido,
    MedioPago,
    ProveedorPago,
)
from apps.autorizacion.tests.base import BaseAPITestCase


class ValidacionAccesoServiceTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        # get_or_create: 'C2P'/'BDV' ya vienen poblados por la migración de seed 0004
        # (catálogos del adaptador BDV, Bloque #3) — no son exclusivos de este test.
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        self.dominio = DominioPermitido.objects.create(aplicacion=self.aplicacion, dominio='conatel.gob.ve')
        AplicacionProveedorPermitido.objects.create(aplicacion=self.aplicacion, proveedor=self.proveedor)

    def test_dominio_app_proveedor_autorizados_retorna_aplicacion(self):
        aplicacion = ValidacionAccesoService.validar(dominio='conatel.gob.ve', proveedor_codigo='BDV')
        self.assertEqual(aplicacion, self.aplicacion)

    def test_dominio_no_registrado_rechaza(self):
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar(dominio='desconocido.com', proveedor_codigo='BDV')
        self.assertEqual(ctx.exception.motivo, 'dominio_no_registrado')

    def test_dominio_inactivo_rechaza(self):
        self.dominio.activo = False
        self.dominio.save()
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar(dominio='conatel.gob.ve', proveedor_codigo='BDV')
        self.assertEqual(ctx.exception.motivo, 'dominio_inactivo')

    def test_aplicacion_inactiva_rechaza(self):
        self.aplicacion.activa = False
        self.aplicacion.save()
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar(dominio='conatel.gob.ve', proveedor_codigo='BDV')
        self.assertEqual(ctx.exception.motivo, 'aplicacion_inactiva')

    def test_proveedor_no_encontrado_rechaza(self):
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar(dominio='conatel.gob.ve', proveedor_codigo='NO_EXISTE')
        self.assertEqual(ctx.exception.motivo, 'proveedor_no_encontrado')

    def test_proveedor_no_autorizado_para_esa_aplicacion_rechaza(self):
        ProveedorPago.objects.create(medio_pago=self.medio_pago, codigo='OTRO', nombre='Otro banco')
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar(dominio='conatel.gob.ve', proveedor_codigo='OTRO')
        self.assertEqual(ctx.exception.motivo, 'proveedor_no_autorizado')

    def test_proveedor_autorizacion_desactivada_rechaza(self):
        AplicacionProveedorPermitido.objects.filter(aplicacion=self.aplicacion, proveedor=self.proveedor).update(activo=False)
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar(dominio='conatel.gob.ve', proveedor_codigo='BDV')
        self.assertEqual(ctx.exception.motivo, 'proveedor_no_autorizado')


class ValidarPorAplicacionTests(BaseAPITestCase):
    """validar_por_aplicacion — usada por el checkout_token en vez de re-derivar el
    dominio del Origin/Referer (Bloque #4)."""

    def setUp(self):
        super().setUp()
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        AplicacionProveedorPermitido.objects.create(aplicacion=self.aplicacion, proveedor=self.proveedor)

    def test_aplicacion_y_proveedor_autorizados_retorna_aplicacion(self):
        aplicacion = ValidacionAccesoService.validar_por_aplicacion(
            aplicacion_id=self.aplicacion.id, proveedor_codigo='BDV',
        )
        self.assertEqual(aplicacion, self.aplicacion)

    def test_aplicacion_no_encontrada_rechaza(self):
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar_por_aplicacion(aplicacion_id=uuid.uuid4(), proveedor_codigo='BDV')
        self.assertEqual(ctx.exception.motivo, 'aplicacion_no_encontrada')

    def test_aplicacion_desactivada_entre_token_y_submit_rechaza(self):
        self.aplicacion.activa = False
        self.aplicacion.save()
        with self.assertRaises(AccesoNoAutorizadoError) as ctx:
            ValidacionAccesoService.validar_por_aplicacion(aplicacion_id=self.aplicacion.id, proveedor_codigo='BDV')
        self.assertEqual(ctx.exception.motivo, 'aplicacion_inactiva')


class ValidarAccesoViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        DominioPermitido.objects.create(aplicacion=self.aplicacion, dominio='conatel.gob.ve')
        AplicacionProveedorPermitido.objects.create(aplicacion=self.aplicacion, proveedor=self.proveedor)

    def test_acceso_autorizado_responde_200_con_checkout_token(self):
        response = self.client.post(
            '/api/autorizacion/validar-acceso/', {'dominio': 'conatel.gob.ve', 'proveedor': 'BDV'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['autorizado'])
        self.assertEqual(response.data['aplicacion'], 'Conatel en Línea')
        self.assertTrue(response.data['checkout_token'])

    def test_acceso_no_autorizado_responde_403_con_motivo(self):
        response = self.client.post(
            '/api/autorizacion/validar-acceso/', {'dominio': 'desconocido.com', 'proveedor': 'BDV'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['autorizado'])
        self.assertEqual(response.data['motivo'], 'dominio_no_registrado')

    def test_payload_invalido_responde_400(self):
        response = self.client.post('/api/autorizacion/validar-acceso/', {'dominio': 'conatel.gob.ve'})
        self.assertEqual(response.status_code, 400)
