from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.conciliacion.infrastructure.bdv_conciliacion_client import (
    BdvConciliacionClient,
    BdvConciliacionNoDisponible,
)


@override_settings(
    BDV_CONCILIACION_BASE_URL='https://bdvconciliacionqa.banvenez.com:444',
    BDV_CONCILIACION_API_KEY='test-api-key',
    BDV_CONCILIACION_TIMEOUT=10.0,
)
class BdvConciliacionClientTests(SimpleTestCase):
    def setUp(self):
        self.client = BdvConciliacionClient()

    @patch('apps.conciliacion.infrastructure.bdv_conciliacion_client.requests.post')
    def test_consulta_exitosa_devuelve_json_crudo(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 1000,
            'message': 'Monto: 120.00 - estatus: Transacción realizada',
            'data': {'status': '1000', 'amount': '120.00', 'reason': 'Transacción realizada', 'referencia': '12345678'},
            'status': 200,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        resultado = self.client.consultar_movimiento(
            cedula_pagador='V27037606', telefono_pagador='04127141363',
            telefono_destino='04127141363', referencia_corta='12345678',
            fecha_pago='2026-08-27', importe='120.00', banco_origen_codigo='0102',
        )

        self.assertEqual(resultado['code'], 1000)
        mock_post.assert_called_once()

    @patch('apps.conciliacion.infrastructure.bdv_conciliacion_client.requests.post')
    def test_envia_headers_y_endpoint_correctos(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {'code': 1000, 'message': '', 'data': None, 'status': 200}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        self.client.consultar_movimiento(
            cedula_pagador='V27037606', telefono_pagador='04127141363',
            telefono_destino='04127141363', referencia_corta='12345678',
            fecha_pago='2026-08-27', importe='120.00', banco_origen_codigo='0102',
        )

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://bdvconciliacionqa.banvenez.com:444/getMovement/v2')
        self.assertEqual(kwargs['headers']['X-API-Key'], 'test-api-key')
        self.assertEqual(kwargs['json']['referencia'], '12345678')
        self.assertEqual(kwargs['timeout'], 10.0)

    @patch('apps.conciliacion.infrastructure.bdv_conciliacion_client.requests.post')
    def test_req_ced_true_solo_en_operacion_intrabanco_bdv(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {'code': 1000, 'message': '', 'data': None, 'status': 200}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        self.client.consultar_movimiento(
            cedula_pagador='V27037606', telefono_pagador='04127141363',
            telefono_destino='04127141363', referencia_corta='12345678',
            fecha_pago='2026-08-27', importe='120.00', banco_origen_codigo='0134',
        )

        self.assertFalse(mock_post.call_args.kwargs['json']['reqCed'])

    @patch('apps.conciliacion.infrastructure.bdv_conciliacion_client.requests.post')
    def test_timeout_de_red_levanta_bdv_conciliacion_no_disponible(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout('timed out')

        with self.assertRaises(BdvConciliacionNoDisponible):
            self.client.consultar_movimiento(
                cedula_pagador='V27037606', telefono_pagador='04127141363',
                telefono_destino='04127141363', referencia_corta='12345678',
                fecha_pago='2026-08-27', importe='120.00', banco_origen_codigo='0102',
            )

    @patch('apps.conciliacion.infrastructure.bdv_conciliacion_client.requests.post')
    def test_http_error_inesperado_levanta_bdv_conciliacion_no_disponible(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('500 Server Error')
        mock_post.return_value = mock_response

        with self.assertRaises(BdvConciliacionNoDisponible):
            self.client.consultar_movimiento(
                cedula_pagador='V27037606', telefono_pagador='04127141363',
                telefono_destino='04127141363', referencia_corta='12345678',
                fecha_pago='2026-08-27', importe='120.00', banco_origen_codigo='0102',
            )
