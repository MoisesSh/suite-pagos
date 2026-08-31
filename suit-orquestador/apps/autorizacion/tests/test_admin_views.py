import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.autorizacion.application.services import FlujoCobroC2PService
from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import (
    Anulacion,
    AplicacionProveedorPermitido,
    AplicacionRegistrada,
    IntencionPago,
    MedioPago,
    ProveedorPago,
)
from apps.autorizacion.domain.puertos_pago import PaymentProviderPort, ResultadoCobro
from apps.autorizacion.tests.base import BaseAPITestCase

User = get_user_model()


class _ConTokenDeStaff(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )
        self.staff = User.objects.create_user(username='admin_conatel', password='x', is_staff=True)
        self.staff_token = Token.objects.create(user=self.staff)
        self.no_staff = User.objects.create_user(username='usuario_comun', password='x', is_staff=False)
        self.no_staff_token = Token.objects.create(user=self.no_staff)

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')


class AdminAplicacionListCreateViewTests(_ConTokenDeStaff):
    def test_crear_sin_token_responde_401(self):
        response = self.client.post(
            '/api/autorizacion/admin/aplicaciones/', {'nombre': 'X', 'dominio': 'x.gob.ve', 'proveedor': 'BDV'},
        )
        self.assertEqual(response.status_code, 401)

    def test_crear_con_usuario_no_staff_responde_403(self):
        self._auth(self.no_staff_token)
        response = self.client.post(
            '/api/autorizacion/admin/aplicaciones/', {'nombre': 'X', 'dominio': 'x.gob.ve', 'proveedor': 'BDV'},
        )
        self.assertEqual(response.status_code, 403)

    def test_crear_con_staff_responde_201_mismo_shape_que_suit_portal(self):
        self._auth(self.staff_token)
        response = self.client.post(
            '/api/autorizacion/admin/aplicaciones/',
            {'nombre': 'Conatel en Línea', 'dominio': 'conatel.gob.ve', 'proveedor': 'BDV'},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data.keys()), {'id', 'nombre', 'dominio', 'proveedor'})
        self.assertEqual(response.data['nombre'], 'Conatel en Línea')
        self.assertEqual(response.data['dominio'], 'conatel.gob.ve')
        self.assertEqual(response.data['proveedor'], 'BDV')

    def test_crear_con_app_origen_id_explicito(self):
        self._auth(self.staff_token)
        app_origen_id = '11111111-1111-1111-1111-111111111111'
        response = self.client.post(
            '/api/autorizacion/admin/aplicaciones/',
            {'nombre': 'X', 'dominio': 'x2.gob.ve', 'proveedor': 'BDV', 'app_origen_id': app_origen_id},
        )
        self.assertEqual(response.status_code, 201)
        aplicacion = AplicacionRegistrada.objects.get(id=response.data['id'])
        self.assertEqual(str(aplicacion.app_origen_id), app_origen_id)

    def test_crear_dominio_duplicado_responde_409(self):
        self._auth(self.staff_token)
        self.client.post(
            '/api/autorizacion/admin/aplicaciones/', {'nombre': 'A', 'dominio': 'dup.gob.ve', 'proveedor': 'BDV'},
        )
        response = self.client.post(
            '/api/autorizacion/admin/aplicaciones/', {'nombre': 'B', 'dominio': 'dup.gob.ve', 'proveedor': 'BDV'},
        )
        self.assertEqual(response.status_code, 409)

    def test_crear_proveedor_no_encontrado_responde_400(self):
        self._auth(self.staff_token)
        response = self.client.post(
            '/api/autorizacion/admin/aplicaciones/', {'nombre': 'X', 'dominio': 'x3.gob.ve', 'proveedor': 'NO_EXISTE'},
        )
        self.assertEqual(response.status_code, 400)

    def test_listar_incluye_dominios_y_proveedores_anidados(self):
        self._auth(self.staff_token)
        self.client.post(
            '/api/autorizacion/admin/aplicaciones/', {'nombre': 'Conatel en Línea', 'dominio': 'lista.gob.ve', 'proveedor': 'BDV'},
        )

        response = self.client.get('/api/autorizacion/admin/aplicaciones/')

        self.assertEqual(response.status_code, 200)
        item = next(a for a in response.data if a['nombre'] == 'Conatel en Línea')
        self.assertEqual(item['dominios'][0]['dominio'], 'lista.gob.ve')
        self.assertEqual(item['proveedores_autorizados'][0]['proveedor'], 'BDV')

    def test_listar_sin_token_responde_401(self):
        response = self.client.get('/api/autorizacion/admin/aplicaciones/')
        self.assertEqual(response.status_code, 401)

    def test_crear_con_webhook_url_genera_secret_visible_en_el_listado(self):
        self._auth(self.staff_token)
        self.client.post('/api/autorizacion/admin/aplicaciones/', {
            'nombre': 'Con Webhook', 'dominio': 'webhook-admin.gob.ve', 'proveedor': 'BDV',
            'webhook_url': 'https://webhook-admin.gob.ve/hook',
        })

        response = self.client.get('/api/autorizacion/admin/aplicaciones/')

        item = next(a for a in response.data if a['nombre'] == 'Con Webhook')
        self.assertEqual(item['webhook_url'], 'https://webhook-admin.gob.ve/hook')
        self.assertTrue(item['webhook_secret'])

    def test_crear_intentando_mandar_webhook_secret_lo_ignora(self):
        # AdminAplicacionCrearSerializer no tiene ese campo — nunca se acepta
        # desde el body, se genera solo (AplicacionRegistrada.save()).
        self._auth(self.staff_token)
        response = self.client.post('/api/autorizacion/admin/aplicaciones/', {
            'nombre': 'X', 'dominio': 'no-acepta-secret.gob.ve', 'proveedor': 'BDV',
            'webhook_url': 'https://x.gob.ve/hook', 'webhook_secret': 'secreto-inventado',
        })
        aplicacion = AplicacionRegistrada.objects.get(id=response.data['id'])
        self.assertNotEqual(aplicacion.webhook_secret, 'secreto-inventado')


class AdminAplicacionActivarViewTests(_ConTokenDeStaff):
    def setUp(self):
        super().setUp()
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        AplicacionProveedorPermitido.objects.create(aplicacion=self.aplicacion, proveedor=self.proveedor)

    def test_desactivar_con_staff(self):
        self._auth(self.staff_token)
        response = self.client.patch(f'/api/autorizacion/admin/aplicaciones/{self.aplicacion.id}/', {'activa': False})

        self.assertEqual(response.status_code, 200)
        self.aplicacion.refresh_from_db()
        self.assertFalse(self.aplicacion.activa)

    def test_activar_sin_token_responde_401(self):
        response = self.client.patch(f'/api/autorizacion/admin/aplicaciones/{self.aplicacion.id}/', {'activa': False})
        self.assertEqual(response.status_code, 401)

    def test_activar_con_no_staff_responde_403(self):
        self._auth(self.no_staff_token)
        response = self.client.patch(f'/api/autorizacion/admin/aplicaciones/{self.aplicacion.id}/', {'activa': False})
        self.assertEqual(response.status_code, 403)

    def test_patch_webhook_url_genera_secret(self):
        self._auth(self.staff_token)
        self.assertEqual(self.aplicacion.webhook_secret, '')

        response = self.client.patch(
            f'/api/autorizacion/admin/aplicaciones/{self.aplicacion.id}/',
            {'webhook_url': 'https://conatel.gob.ve/hook'},
        )

        self.assertEqual(response.status_code, 200)
        self.aplicacion.refresh_from_db()
        self.assertEqual(self.aplicacion.webhook_url, 'https://conatel.gob.ve/hook')
        self.assertTrue(self.aplicacion.webhook_secret)

    def test_patch_solo_activa_no_toca_webhook_url(self):
        self.aplicacion.webhook_url = 'https://ya-configurado.gob.ve/hook'
        self.aplicacion.save()
        secret_original = self.aplicacion.webhook_secret
        self._auth(self.staff_token)

        response = self.client.patch(f'/api/autorizacion/admin/aplicaciones/{self.aplicacion.id}/', {'activa': False})

        self.assertEqual(response.status_code, 200)
        self.aplicacion.refresh_from_db()
        self.assertEqual(self.aplicacion.webhook_url, 'https://ya-configurado.gob.ve/hook')
        self.assertEqual(self.aplicacion.webhook_secret, secret_original)


class AdminAnularPagoViewTests(_ConTokenDeStaff):
    def setUp(self):
        super().setUp()
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        self.pago = FlujoCobroC2PService.iniciar(
            aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES',
        )
        adaptador_cobro = Mock(spec=PaymentProviderPort)
        adaptador_cobro.procesar_cobro.return_value = ResultadoCobro(
            codigo='1000', mensaje='Proceso finalizado', referencia_corta='090037579602',
            identificador_interbancario='0102010298400079090940416589264220251114162931090620472770',
            payload_crudo={'code': '1000'},
        )
        FlujoCobroC2PService.ejecutar_cobro(
            self.pago, adaptador=adaptador_cobro, cedula_pagador='V12345678', telefono_pagador='04125692243',
            banco_codigo='0102', concepto='Pago', otp='5551111', telefono_comercio='04140282647',
        )
        self.pago.refresh_from_db()

    def _url(self):
        return f'/api/autorizacion/admin/pagos/{self.pago.id}/anular/'

    def test_anular_sin_token_responde_401(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 401)

    def test_anular_con_usuario_no_staff_responde_403(self):
        self._auth(self.no_staff_token)
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 403)

    @patch('apps.autorizacion.api.admin_views.BDVPagoMovilC2PAdapter')
    def test_anular_con_staff_exitoso_responde_200_y_transiciona_a_anulado(self, MockAdaptador):
        MockAdaptador.return_value.anular.return_value = Mock(
            codigo='1000', mensaje='Proceso finalizado', payload_crudo={'code': '1000'},
        )
        self._auth(self.staff_token)

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 200)
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.estado_actual, IntencionPago.EstadoPago.ANULADO)
        self.assertEqual(Anulacion.objects.filter(pago=self.pago).count(), 1)
        self.assertEqual(response.data['estado_pago'], IntencionPago.EstadoPago.ANULADO)

    @patch('apps.autorizacion.api.admin_views.BDVPagoMovilC2PAdapter')
    def test_anular_rechazado_por_proveedor_responde_409_y_no_transiciona(self, MockAdaptador):
        MockAdaptador.return_value.anular.side_effect = ProveedorPagoError(
            codigo='1050', mensaje='La solicitud superó el Timeout',
        )
        self._auth(self.staff_token)

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['codigo_proveedor'], '1050')
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.estado_actual, IntencionPago.EstadoPago.CAPTURADO)

    @patch('apps.autorizacion.api.admin_views.BDVPagoMovilC2PAdapter')
    def test_anular_proveedor_indisponible_responde_503(self, MockAdaptador):
        MockAdaptador.return_value.anular.side_effect = ProveedorPagoIndisponibleError('timeout')
        self._auth(self.staff_token)

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 503)
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.estado_actual, IntencionPago.EstadoPago.CAPTURADO)

    @patch('apps.autorizacion.api.admin_views.BDVPagoMovilC2PAdapter')
    def test_anular_pago_pendiente_responde_409_pago_no_anulable(self, MockAdaptador):
        otro_pago = FlujoCobroC2PService.iniciar(
            aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES',
        )
        self._auth(self.staff_token)

        response = self.client.post(f'/api/autorizacion/admin/pagos/{otro_pago.id}/anular/')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error'], 'pago_no_anulable')
        MockAdaptador.return_value.anular.assert_not_called()
