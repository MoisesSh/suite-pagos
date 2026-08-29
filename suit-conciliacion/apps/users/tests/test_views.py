from rest_framework import status

from apps.shared.tests import factories
from apps.shared.tests.base import BaseAPITestCase


class LoginViewTests(BaseAPITestCase):
    def test_login_exitoso_no_expone_refresh_en_el_body(self):
        # Auditoría de seguridad (Bloque #16): el refresh solo viaja en la
        # cookie HttpOnly, nunca en el body — devolverlo ahí también anula
        # la protección HttpOnly a nivel de contrato de API.
        usuario = factories.crear_usuario(email='login-test@conciliacion.test', password='ClaveSegura123!')

        response = self.client.post(
            '/api/auth/login/', {'email': 'login-test@conciliacion.test', 'password': 'ClaveSegura123!'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('usuario', response.data)
        self.assertNotIn('refresh', response.data)
        self.assertIn('refresh_token', response.cookies)
        self.assertTrue(response.cookies['refresh_token']['httponly'])

    def test_login_credenciales_invalidas(self):
        response = self.client.post(
            '/api/auth/login/', {'email': 'no-existe@conciliacion.test', 'password': 'loquesea'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CookieTokenRefreshViewTests(BaseAPITestCase):
    def test_refresh_exitoso_no_expone_refresh_en_el_body(self):
        usuario = factories.crear_usuario(email='refresh-test@conciliacion.test', password='ClaveSegura123!')
        login = self.client.post(
            '/api/auth/login/', {'email': 'refresh-test@conciliacion.test', 'password': 'ClaveSegura123!'},
            format='json',
        )
        self.client.cookies['refresh_token'] = login.cookies['refresh_token'].value

        response = self.client.post('/api/auth/refresh/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        self.assertIn('refresh_token', response.cookies)

    def test_refresh_sin_token_devuelve_401(self):
        response = self.client.post('/api/auth/refresh/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
