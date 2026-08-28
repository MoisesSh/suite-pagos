from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from config.urls import embebible_desde_portal


@override_settings(PORTAL_ORIGIN='http://localhost:3001')
class EmbebibleDesdePortalTests(TestCase):
    """Testea `embebible_desde_portal` en aislamiento (RequestFactory), no vía
    `/api/docs/`/`/api/schema/` reales: esas rutas se registran en
    config/urls.py solo `if settings.DEBUG:` AL IMPORTAR el módulo, y
    `manage.py test` fuerza DEBUG=False durante toda la corrida — para cuando
    un test corre, el módulo ya fue importado con esas rutas ausentes, y
    forzar DEBUG/ROOT_URLCONF vía override_settings no re-ejecuta el import
    (Python ya tiene `config.urls` en sys.modules). Este test cubre lo que
    realmente cambió: el wrapper agrega el header correcto y exime
    X-Frame-Options — no la decisión (preexistente) de gatear las rutas por
    DEBUG."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_agrega_csp_frame_ancestors_con_el_origen_del_portal(self):
        vista_wrappeada = embebible_desde_portal(lambda request: HttpResponse('ok'))
        response = vista_wrappeada(self.factory.get('/cualquier-vista/'))

        self.assertEqual(response['Content-Security-Policy'], "frame-ancestors 'self' http://localhost:3001")

    def test_exime_x_frame_options_para_permitir_el_iframe(self):
        vista_wrappeada = embebible_desde_portal(lambda request: HttpResponse('ok'))
        response = vista_wrappeada(self.factory.get('/cualquier-vista/'))

        self.assertTrue(getattr(response, 'xframe_options_exempt', False))

    def test_resto_del_proyecto_sigue_en_deny_por_default(self):
        response = self.client.get('/api/auth/login/')
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')
