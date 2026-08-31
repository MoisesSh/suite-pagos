import unittest
from decimal import Decimal

from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase

from apps.conciliacion.domain.models import LineaLedger, TransaccionLedger
from apps.shared.tests import factories


@unittest.skipUnless(
    connection.vendor == 'postgresql',
    'El trigger de balance-cero (migración 0003) es PL/pgSQL puro — no existe en '
    'sqlite (no-op ahí, ver 0003_ledger_balance_trigger.py). Solo corre contra '
    'Postgres real, único entorno donde esta regresión es detectable: un `%` sin '
    'escapar en el RAISE EXCEPTION rompía la migración con '
    '"psycopg.ProgrammingError: incomplete placeholder" al aplicarse contra '
    'Postgres real (nunca contra sqlite, donde es no-op) — encontrado recién al '
    'levantar el stack completo en Docker.',
)
class LedgerBalanceTriggerTests(TransactionTestCase):
    """`TransactionTestCase`, no `TestCase`: el trigger es
    `DEFERRABLE INITIALLY DEFERRED` — solo se evalúa en un COMMIT real.
    `TestCase` envuelve cada test en una transacción que nunca comitea de
    verdad (solo rollback), así que un `with transaction.atomic()` anidado
    ahí nunca dispara el trigger — el error aparecería recién en el teardown
    del framework, no en el test."""
    def setUp(self):
        self.evento = factories.crear_evento_pago()
        self.cuenta_debito = factories.crear_cuenta_contable(codigo='1105', nombre='Banco')
        self.cuenta_credito = factories.crear_cuenta_contable(codigo='4105', nombre='Ingresos por conciliar')

    def test_transaccion_balanceada_se_guarda_sin_error(self):
        with transaction.atomic():
            transaccion = TransaccionLedger.objects.create(
                referencia_evento=self.evento, aplicacion_id=self.evento.payload['aplicacion_id'],
            )
            LineaLedger.objects.create(
                transaccion=transaccion, cuenta=self.cuenta_debito,
                tipo=LineaLedger.Tipo.DEBITO, monto=Decimal('100.00'),
            )
            LineaLedger.objects.create(
                transaccion=transaccion, cuenta=self.cuenta_credito,
                tipo=LineaLedger.Tipo.CREDITO, monto=Decimal('100.00'),
            )

        self.assertEqual(LineaLedger.objects.filter(transaccion=transaccion).count(), 2)

    def test_transaccion_desbalanceada_falla_al_commitear(self):
        # El constraint trigger es DEFERRABLE INITIALLY DEFERRED: se evalúa al
        # COMMIT del bloque atomic, no en cada INSERT — por eso el error aparece
        # recién al salir del `with transaction.atomic()`, no en el segundo create().
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                transaccion = TransaccionLedger.objects.create(
                    referencia_evento=self.evento, aplicacion_id=self.evento.payload['aplicacion_id'],
                )
                LineaLedger.objects.create(
                    transaccion=transaccion, cuenta=self.cuenta_debito,
                    tipo=LineaLedger.Tipo.DEBITO, monto=Decimal('100.00'),
                )
                LineaLedger.objects.create(
                    transaccion=transaccion, cuenta=self.cuenta_credito,
                    tipo=LineaLedger.Tipo.CREDITO, monto=Decimal('50.00'),
                )
