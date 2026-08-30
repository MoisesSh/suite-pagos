import uuid

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.autorizacion.domain.models import AplicacionProveedorPermitido, AplicacionRegistrada, MedioPago, ProveedorPago
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
