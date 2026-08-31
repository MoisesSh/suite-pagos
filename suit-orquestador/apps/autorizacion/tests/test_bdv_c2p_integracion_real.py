import os
import unittest
import uuid
from decimal import Decimal

from django.conf import settings
from django.test import TestCase

from apps.autorizacion.application.services import FlujoCobroC2PService
from apps.autorizacion.domain.models import Anulacion, AplicacionRegistrada, Captura, IntencionPago
from apps.autorizacion.infrastructure.adapters.bdv_c2p import BDVPagoMovilC2PAdapter

# Pega de verdad al QA de BDV (bdvconciliacionqa.banvenez.com) — nunca corre en un
# `manage.py test` normal ni en CI. Requiere BDV_C2P_API_KEY/BDV_C2P_BASE_URL reales
# (ver .env, no .env.example) y el opt-in explícito RUN_BDV_QA_INTEGRATION=1, porque
# hace un cobro real (aunque sea el dummy QA de 1000.6) seguido de su anulación.
_QA_DISPONIBLE = bool(settings.BDV_C2P_API_KEY) and os.environ.get('RUN_BDV_QA_INTEGRATION') == '1'


@unittest.skipUnless(
    _QA_DISPONIBLE,
    'Requiere BDV_C2P_API_KEY configurada y RUN_BDV_QA_INTEGRATION=1 (integración real contra BDV QA).',
)
class BDVC2PAnulacionIntegracionRealTests(TestCase):
    """anular() no tiene forma de probarse de verdad sin un endToEndId real —
    solo lo emite BDV en la respuesta de un cobro ya procesado. Por eso este test
    corre el flujo completo cobro -> anulación contra el QA real, no mocks
    (a diferencia de test_bdv_c2p_adapter.py y test_flujo_cobro_c2p.py)."""

    def setUp(self):
        self.aplicacion = AplicacionRegistrada.objects.create(
            nombre='Integración QA BDV', app_origen_id=uuid.uuid4(),
        )
        self.adaptador = BDVPagoMovilC2PAdapter()

    def test_cobro_real_seguido_de_anulacion_real(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.6'), moneda_codigo='VES')

        _autorizacion, captura = FlujoCobroC2PService.ejecutar_cobro(
            pago, adaptador=self.adaptador,
            cedula_pagador='V12345678', telefono_pagador='04125692243', banco_codigo='0102',
            concepto='Pago', otp='5551111', telefono_comercio=settings.BDV_C2P_TELEFONO_COMERCIO,
        )
        pago.refresh_from_db()
        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.CAPTURADO)
        self.assertTrue(captura.identificador_interbancario)

        anulacion = FlujoCobroC2PService.anular_cobro(pago, adaptador=self.adaptador)

        pago.refresh_from_db()
        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.ANULADO)
        self.assertIsInstance(anulacion, Anulacion)
        self.assertEqual(anulacion.identificador_interbancario, captura.identificador_interbancario)
        self.assertEqual(Captura.objects.filter(pago=pago).count(), 1)
