from decimal import Decimal

from rest_framework import status

from apps.conciliacion.application.services.ledger import LedgerService
from apps.shared.tests import factories
from apps.shared.tests.base import BaseAPITestCase


class EventoPagoRecibidoListViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.usuario = factories.crear_usuario()

    def test_requiere_autenticacion(self):
        response = self.client.get('/api/conciliacion/eventos/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_evento_sin_transaccion_ledger_asociada_devuelve_id_null(self):
        factories.crear_evento_pago()

        self.client.force_authenticate(self.usuario)
        response = self.client.get('/api/conciliacion/eventos/')

        resultados = response.data['results']
        self.assertEqual(len(resultados), 1)
        self.assertIsNone(resultados[0]['transaccion_ledger_id'])

    def test_evento_conciliado_expone_transaccion_ledger_id(self):
        cuenta_debito = factories.crear_cuenta_contable(codigo='1105', nombre='Banco')
        cuenta_credito = factories.crear_cuenta_contable(codigo='4105', nombre='Ingresos por conciliar')
        evento = factories.crear_evento_pago()
        transaccion = LedgerService.registrar_transaccion(evento, [
            {'cuenta': cuenta_debito, 'tipo': 'debito', 'monto': Decimal('100.00')},
            {'cuenta': cuenta_credito, 'tipo': 'credito', 'monto': Decimal('100.00')},
        ])

        self.client.force_authenticate(self.usuario)
        response = self.client.get('/api/conciliacion/eventos/')

        resultados = response.data['results']
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['transaccion_ledger_id'], transaccion.id)
