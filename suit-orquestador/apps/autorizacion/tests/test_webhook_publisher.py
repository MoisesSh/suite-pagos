import hashlib
import hmac
import json
from unittest.mock import Mock, patch

import requests

from apps.autorizacion.infrastructure.webhook_publisher import WebhookEntregaFallidaError, WebhookPublisher
from apps.autorizacion.tests.base import BaseAPITestCase


class WebhookPublisherTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.publisher = WebhookPublisher(timeout=5)

    @patch('apps.autorizacion.infrastructure.webhook_publisher.requests.post')
    def test_entrega_exitosa_firma_correctamente_y_devuelve_status(self, mock_post):
        mock_post.return_value = Mock(status_code=200)

        status_code = self.publisher.entregar(
            webhook_url='https://conatel.gob.ve/webhooks/suit-pagos',
            webhook_secret='clave-secreta',
            event_id='06a90fa3-ed05-7d59-8000-21ece2e83043',
            event_type='pago.confirmado',
            payload={'pago_id': 'abc'},
            schema_version=1,
        )

        self.assertEqual(status_code, 200)
        llamada = mock_post.call_args
        self.assertEqual(llamada.args[0], 'https://conatel.gob.ve/webhooks/suit-pagos')
        cuerpo_enviado = llamada.kwargs['data']
        firma_enviada = llamada.kwargs['headers']['X-Suit-Signature']

        # La firma debe ser HMAC-SHA256 del cuerpo EXACTO enviado, con la clave
        # de esa app — recalculada acá para verificar que coincide byte a byte.
        firma_esperada = 'sha256=' + hmac.new(b'clave-secreta', cuerpo_enviado, hashlib.sha256).hexdigest()
        self.assertEqual(firma_enviada, firma_esperada)

        envelope = json.loads(cuerpo_enviado)
        self.assertEqual(envelope['event_id'], '06a90fa3-ed05-7d59-8000-21ece2e83043')
        self.assertEqual(envelope['event_type'], 'pago.confirmado')
        self.assertEqual(envelope['schema_version'], 1)
        self.assertEqual(envelope['payload'], {'pago_id': 'abc'})

    @patch('apps.autorizacion.infrastructure.webhook_publisher.requests.post')
    def test_status_no_2xx_lanza_entrega_fallida_con_status_code(self, mock_post):
        mock_post.return_value = Mock(status_code=500)

        with self.assertRaises(WebhookEntregaFallidaError) as ctx:
            self.publisher.entregar(
                webhook_url='https://conatel.gob.ve/webhooks/suit-pagos', webhook_secret='clave',
                event_id='x', event_type='pago.confirmado', payload={}, schema_version=1,
            )
        self.assertEqual(ctx.exception.status_code, 500)

    @patch('apps.autorizacion.infrastructure.webhook_publisher.requests.post')
    def test_timeout_lanza_entrega_fallida_sin_status_code(self, mock_post):
        mock_post.side_effect = requests.Timeout('tiempo agotado')

        with self.assertRaises(WebhookEntregaFallidaError) as ctx:
            self.publisher.entregar(
                webhook_url='https://conatel.gob.ve/webhooks/suit-pagos', webhook_secret='clave',
                event_id='x', event_type='pago.confirmado', payload={}, schema_version=1,
            )
        self.assertIsNone(ctx.exception.status_code)

    @patch('apps.autorizacion.infrastructure.webhook_publisher.requests.post')
    def test_usa_timeout_configurado(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        self.publisher.entregar(
            webhook_url='https://x.com/hook', webhook_secret='k', event_id='x',
            event_type='pago.confirmado', payload={}, schema_version=1,
        )
        self.assertEqual(mock_post.call_args.kwargs['timeout'], 5)
