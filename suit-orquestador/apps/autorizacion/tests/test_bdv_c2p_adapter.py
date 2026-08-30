from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import override_settings

from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.infrastructure.adapters.bdv_c2p import BDVPagoMovilC2PAdapter
from apps.autorizacion.tests.base import BaseAPITestCase


def _response_mock(json_data, status_code=200, raise_for_status_side_effect=None):
    response = Mock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.raise_for_status.side_effect = raise_for_status_side_effect
    return response


class BDVPagoMovilC2PAdapterTests(BaseAPITestCase):
    """Mockea requests.post — es la implementación bajo prueba, no un detalle externo
    a esconder (testing-backend-django: mockear en el punto de entrada del service)."""

    def setUp(self):
        super().setUp()
        self.adaptador = BDVPagoMovilC2PAdapter(
            base_url='https://bdvconciliacionqa.banvenez.com:444', api_key='dummy-key', timeout=5,
        )

    @override_settings(BDV_C2P_BASE_URL=None)
    def test_sin_base_url_configurada_lanza_runtime_error(self):
        # Hallazgo de seguridad: BDV_C2P_BASE_URL ya no cae por default al QA real
        # del banco — sin la env var, debe fallar explícito, no silenciosamente.
        with self.assertRaises(RuntimeError):
            BDVPagoMovilC2PAdapter(api_key='dummy-key')

    @patch('apps.autorizacion.infrastructure.adapters.bdv_c2p.requests.post')
    def test_generar_otp_exitoso(self, mock_post):
        mock_post.return_value = _response_mock({'code': '1000', 'message': 'Proceso finalizado', 'data': None, 'status': 200})

        resultado = self.adaptador.generar_otp(cedula='V12345678')

        self.assertEqual(resultado.codigo, '1000')
        mock_post.assert_called_once_with(
            'https://bdvconciliacionqa.banvenez.com:444/BankMobilePaymentC2P/MultipleAccounts/paymentkey/v2',
            json={'customerDocumentId': 'V12345678'},
            headers={'X-API-Key': 'dummy-key', 'Content-Type': 'application/json'},
            timeout=5,
        )

    @patch('apps.autorizacion.infrastructure.adapters.bdv_c2p.requests.post')
    def test_generar_otp_error_negocio_lanza_proveedor_pago_error(self, mock_post):
        mock_post.return_value = _response_mock({'code': '1080', 'message': 'Documento de identidad inválido', 'data': None, 'status': 200})

        with self.assertRaises(ProveedorPagoError) as ctx:
            self.adaptador.generar_otp(cedula='invalido')
        self.assertEqual(ctx.exception.codigo, '1080')

    @patch('apps.autorizacion.infrastructure.adapters.bdv_c2p.requests.post')
    def test_procesar_cobro_exitoso_retorna_referencias(self, mock_post):
        mock_post.return_value = _response_mock({
            'code': '1000',
            'message': 'Proceso finalizado',
            'data': {
                'date': '2025-11-14',
                'endToEndId': '0102010298400079090940416589264220251114162931090620472770',
                'cuenta': None,
                'saldoDisponible': None,
                'cuentaDivisa': None,
                'saldoCuentaDivisa': None,
                'referencia': '090037579602',
            },
            'status': 200,
        })

        resultado = self.adaptador.procesar_cobro(
            cedula='V12345678', telefono_pagador='04125692243', monto=Decimal('1000.60'),
            banco_codigo='0102', concepto='Pago', otp='5551111', moneda_codigo='VES',
            tipo_operacion_codigo='CELE', telefono_comercio='04140282647',
        )

        self.assertEqual(resultado.referencia_corta, '090037579602')
        self.assertEqual(resultado.identificador_interbancario, '0102010298400079090940416589264220251114162931090620472770')
        sent_body = mock_post.call_args.kwargs['json']
        self.assertEqual(sent_body['amount'], '1000.60')

    @patch('apps.autorizacion.infrastructure.adapters.bdv_c2p.requests.post')
    def test_procesar_cobro_error_lanza_proveedor_pago_error_con_codigo(self, mock_post):
        mock_post.return_value = _response_mock({'code': '1034', 'message': 'Saldo insuficiente', 'data': None, 'status': 200})

        with self.assertRaises(ProveedorPagoError) as ctx:
            self.adaptador.procesar_cobro(
                cedula='V12345678', telefono_pagador='04125692243', monto=Decimal('1000.60'),
                banco_codigo='0102', concepto='Pago', otp='0000', moneda_codigo='VES',
                tipo_operacion_codigo='CELE', telefono_comercio='04140282647',
            )
        self.assertEqual(ctx.exception.codigo, '1034')

    @patch('apps.autorizacion.infrastructure.adapters.bdv_c2p.requests.post')
    def test_timeout_lanza_proveedor_pago_indisponible_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.Timeout('tiempo agotado')

        with self.assertRaises(ProveedorPagoIndisponibleError):
            self.adaptador.generar_otp(cedula='V12345678')

    @patch('apps.autorizacion.infrastructure.adapters.bdv_c2p.requests.post')
    def test_anular_exitoso(self, mock_post):
        mock_post.return_value = _response_mock({
            'code': '1000',
            'message': 'Proceso finalizado',
            'data': {'date': '2025-11-14', 'endToEndId': None, 'cuenta': None, 'saldoDisponible': None, 'cuentaDivisa': None, 'saldoCuentaDivisa': None, 'referencia': None},
            'status': 200,
        })

        resultado = self.adaptador.anular(identificador_interbancario='0102010298400079090940416589264220251114162931090620472770')

        self.assertEqual(resultado.codigo, '1000')
        sent_body = mock_post.call_args.kwargs['json']
        self.assertEqual(sent_body['endToEndId'], '0102010298400079090940416589264220251114162931090620472770')
        self.assertIsNone(sent_body['referenceOrigin'])
