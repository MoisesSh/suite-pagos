import uuid

from apps.autorizacion.application.services import (
    DominioYaRegistradoError,
    ProveedorNoEncontradoError,
    RegistroAplicacionService,
)
from apps.autorizacion.domain.models import (
    AplicacionProveedorPermitido,
    DominioPermitido,
    MedioPago,
    ProveedorPago,
)
from apps.autorizacion.tests.base import BaseAPITestCase


class RegistroAplicacionServiceTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )

    def test_registrar_crea_aplicacion_dominio_y_autorizacion(self):
        aplicacion = RegistroAplicacionService.registrar(
            nombre='Conatel en Línea', dominio='conatel.gob.ve', proveedor_codigo='BDV',
        )

        self.assertTrue(aplicacion.activa)
        self.assertIsNotNone(aplicacion.app_origen_id)
        self.assertTrue(DominioPermitido.objects.filter(aplicacion=aplicacion, dominio='conatel.gob.ve').exists())
        self.assertTrue(
            AplicacionProveedorPermitido.objects.filter(aplicacion=aplicacion, proveedor=self.proveedor).exists(),
        )

    def test_registrar_con_app_origen_id_explicito_lo_respeta(self):
        app_origen_id = uuid.uuid4()
        aplicacion = RegistroAplicacionService.registrar(
            nombre='Homologación', dominio='homologacion.gob.ve', proveedor_codigo='BDV',
            app_origen_id=app_origen_id,
        )
        self.assertEqual(aplicacion.app_origen_id, app_origen_id)

    def test_registrar_sin_app_origen_id_genera_uno_propio(self):
        a1 = RegistroAplicacionService.registrar(nombre='App 1', dominio='app1.gob.ve', proveedor_codigo='BDV')
        a2 = RegistroAplicacionService.registrar(nombre='App 2', dominio='app2.gob.ve', proveedor_codigo='BDV')
        self.assertNotEqual(a1.app_origen_id, a2.app_origen_id)

    def test_proveedor_no_encontrado_lanza_error(self):
        with self.assertRaises(ProveedorNoEncontradoError):
            RegistroAplicacionService.registrar(nombre='X', dominio='x.gob.ve', proveedor_codigo='NO_EXISTE')

    def test_dominio_duplicado_lanza_error_y_no_deja_restos(self):
        RegistroAplicacionService.registrar(nombre='App 1', dominio='duplicado.gob.ve', proveedor_codigo='BDV')

        with self.assertRaises(DominioYaRegistradoError):
            RegistroAplicacionService.registrar(nombre='App 2', dominio='duplicado.gob.ve', proveedor_codigo='BDV')

        # La transacción de la segunda llamada se revierte completa: no queda una
        # AplicacionRegistrada 'App 2' huérfana sin su dominio.
        from apps.autorizacion.domain.models import AplicacionRegistrada
        self.assertEqual(AplicacionRegistrada.objects.filter(nombre='App 2').count(), 0)

    def test_activar_desactivar(self):
        aplicacion = RegistroAplicacionService.registrar(
            nombre='Conatel en Línea', dominio='conatel2.gob.ve', proveedor_codigo='BDV',
        )
        RegistroAplicacionService.activar_desactivar(aplicacion, False)
        aplicacion.refresh_from_db()
        self.assertFalse(aplicacion.activa)

        RegistroAplicacionService.activar_desactivar(aplicacion, True)
        aplicacion.refresh_from_db()
        self.assertTrue(aplicacion.activa)
