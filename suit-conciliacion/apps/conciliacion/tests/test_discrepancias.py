import uuid

from django.test import TestCase
from rest_framework import status

from apps.conciliacion.application.services.matching import MatchingService
from apps.conciliacion.domain.models import Discrepancia
from apps.shared.tests import factories
from apps.shared.tests.base import BaseAPITestCase


def _crear_discrepancia(**overrides):
    defaults = {
        'evento': factories.crear_evento_pago(),
        'tipo': Discrepancia.Tipo.SIN_MOVIMIENTO_BANCARIO,
        'severidad': Discrepancia.Severidad.MEDIA,
    }
    defaults.update(overrides)
    return Discrepancia.objects.create(**defaults)


class ResolverDiscrepanciaServiceTests(TestCase):
    def test_resolver_discrepancia_setea_usuario_estado_y_timestamp(self):
        usuario = factories.crear_usuario()
        discrepancia = _crear_discrepancia()

        resultado = MatchingService.resolver_discrepancia(
            discrepancia,
            usuario=usuario,
            estado_resolucion=Discrepancia.EstadoResolucion.RESUELTA,
            notas='Confirmado manualmente contra el estado de cuenta.',
        )

        self.assertEqual(resultado.estado_resolucion, Discrepancia.EstadoResolucion.RESUELTA)
        self.assertEqual(resultado.resuelto_por, usuario)
        self.assertIsNotNone(resultado.resuelto_at)
        self.assertEqual(resultado.notas, 'Confirmado manualmente contra el estado de cuenta.')

    def test_resolver_discrepancia_sin_notas_no_pisa_las_existentes(self):
        usuario = factories.crear_usuario()
        discrepancia = _crear_discrepancia(notas='Nota original.')

        resultado = MatchingService.resolver_discrepancia(
            discrepancia, usuario=usuario, estado_resolucion=Discrepancia.EstadoResolucion.EN_REVISION,
        )

        self.assertEqual(resultado.notas, 'Nota original.')


class DiscrepanciaListViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.usuario = factories.crear_usuario()

    def test_requiere_autenticacion(self):
        response = self.client.get('/api/conciliacion/discrepancias/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lista_discrepancias_filtrando_por_estado_resolucion(self):
        _crear_discrepancia(estado_resolucion=Discrepancia.EstadoResolucion.ABIERTA)
        _crear_discrepancia(estado_resolucion=Discrepancia.EstadoResolucion.RESUELTA)

        self.client.force_authenticate(self.usuario)
        response = self.client.get('/api/conciliacion/discrepancias/', {'estado_resolucion': 'abierta'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultados = response.data['results']
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['estado_resolucion'], 'abierta')

    def test_lista_discrepancias_filtrando_por_severidad(self):
        _crear_discrepancia(severidad=Discrepancia.Severidad.CRITICA)
        _crear_discrepancia(severidad=Discrepancia.Severidad.BAJA)

        self.client.force_authenticate(self.usuario)
        response = self.client.get('/api/conciliacion/discrepancias/', {'severidad': 'critica'})

        resultados = response.data['results']
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['severidad'], 'critica')


class DiscrepanciaResolverViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        # is_staff=True: resolver es una acción de mutación de datos de
        # conciliación/auditoría, restringida a staff (IsAdminUser) — un
        # Usuario de solo consulta (is_staff=False) puede listar, no resolver.
        self.usuario = factories.crear_usuario(is_staff=True)

    def test_staff_de_solo_consulta_no_puede_resolver(self):
        usuario_solo_consulta = factories.crear_usuario(is_staff=False)
        discrepancia = _crear_discrepancia()
        self.client.force_authenticate(usuario_solo_consulta)

        response = self.client.patch(
            f'/api/conciliacion/discrepancias/{discrepancia.id}/resolver/',
            {'estado_resolucion': 'resuelta'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resolver_discrepancia_marca_resuelta_por_usuario_autenticado(self):
        discrepancia = _crear_discrepancia()
        self.client.force_authenticate(self.usuario)

        response = self.client.patch(
            f'/api/conciliacion/discrepancias/{discrepancia.id}/resolver/',
            {'estado_resolucion': 'resuelta', 'notas': 'Verificado en el estado de cuenta del banco.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        discrepancia.refresh_from_db()
        self.assertEqual(discrepancia.estado_resolucion, 'resuelta')
        self.assertEqual(discrepancia.resuelto_por, self.usuario)
        self.assertIsNotNone(discrepancia.resuelto_at)

    def test_resolver_requiere_autenticacion(self):
        discrepancia = _crear_discrepancia()
        response = self.client.patch(
            f'/api/conciliacion/discrepancias/{discrepancia.id}/resolver/',
            {'estado_resolucion': 'resuelta'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resolver_discrepancia_inexistente_devuelve_404(self):
        self.client.force_authenticate(self.usuario)
        response = self.client.patch(
            f'/api/conciliacion/discrepancias/{uuid.uuid4()}/resolver/',
            {'estado_resolucion': 'resuelta'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_estado_resolucion_no_permitido_devuelve_400(self):
        discrepancia = _crear_discrepancia()
        self.client.force_authenticate(self.usuario)

        response = self.client.patch(
            f'/api/conciliacion/discrepancias/{discrepancia.id}/resolver/',
            {'estado_resolucion': 'abierta'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
