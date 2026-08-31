import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.conciliacion.application.services.ledger import LedgerService
from apps.conciliacion.domain.models import LineaLedger
from apps.shared.tests import factories
from apps.shared.tests.base import BaseAPITestCase


def _lineas(cuenta_debito, cuenta_credito, monto=Decimal('100.00')):
    return [
        {'cuenta': cuenta_debito, 'tipo': LineaLedger.Tipo.DEBITO, 'monto': monto},
        {'cuenta': cuenta_credito, 'tipo': LineaLedger.Tipo.CREDITO, 'monto': monto},
    ]


class LedgerServiceTests(TestCase):
    def setUp(self):
        self.cuenta_debito = factories.crear_cuenta_contable(codigo='1105', nombre='Banco')
        self.cuenta_credito = factories.crear_cuenta_contable(codigo='4105', nombre='Ingresos por conciliar')

    def test_registrar_transaccion_extrae_aplicacion_id_del_payload_del_evento(self):
        aplicacion_id = str(uuid.uuid4())
        evento = factories.crear_evento_pago(payload={'monto': '100.00', 'aplicacion_id': aplicacion_id})

        transaccion = LedgerService.registrar_transaccion(
            evento, _lineas(self.cuenta_debito, self.cuenta_credito),
        )

        self.assertEqual(str(transaccion.aplicacion_id), aplicacion_id)


class TransaccionLedgerListViewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.usuario = factories.crear_usuario()
        self.cuenta_debito = factories.crear_cuenta_contable(codigo='1105', nombre='Banco')
        self.cuenta_credito = factories.crear_cuenta_contable(codigo='4105', nombre='Ingresos por conciliar')

    def test_requiere_autenticacion(self):
        response = self.client.get('/api/conciliacion/transacciones-ledger/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lista_transacciones_filtrando_por_aplicacion_id(self):
        aplicacion_id = str(uuid.uuid4())
        evento_propio = factories.crear_evento_pago(payload={'monto': '50.00', 'aplicacion_id': aplicacion_id})
        evento_otra_app = factories.crear_evento_pago()

        LedgerService.registrar_transaccion(evento_propio, _lineas(self.cuenta_debito, self.cuenta_credito))
        LedgerService.registrar_transaccion(evento_otra_app, _lineas(self.cuenta_debito, self.cuenta_credito))

        self.client.force_authenticate(self.usuario)
        response = self.client.get('/api/conciliacion/transacciones-ledger/', {'aplicacion_id': aplicacion_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultados = response.data['results']
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['aplicacion_id'], aplicacion_id)

    def test_sin_filtro_lista_todas(self):
        evento_a = factories.crear_evento_pago()
        evento_b = factories.crear_evento_pago()
        LedgerService.registrar_transaccion(evento_a, _lineas(self.cuenta_debito, self.cuenta_credito))
        LedgerService.registrar_transaccion(evento_b, _lineas(self.cuenta_debito, self.cuenta_credito))

        self.client.force_authenticate(self.usuario)
        response = self.client.get('/api/conciliacion/transacciones-ledger/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
