import uuid
from decimal import Decimal
from unittest.mock import Mock

from django.test import override_settings

from apps.autorizacion.application.services import FlujoCobroC2PService
from apps.autorizacion.application.services.webhook_relay import WebhookRelayService
from apps.autorizacion.domain.models import AplicacionRegistrada, EventoOutbox, WebhookEntrega
from apps.autorizacion.infrastructure.webhook_publisher import WebhookEntregaFallidaError
from apps.autorizacion.tests.base import BaseAPITestCase


class WebhookRelayServiceTests(BaseAPITestCase):
    """Mockea WebhookPublisher — no hace requests HTTP reales en el test suite."""

    def setUp(self):
        super().setUp()
        self.aplicacion = AplicacionRegistrada.objects.create(
            nombre='Conatel en Línea', app_origen_id=uuid.uuid4(), webhook_url='https://conatel.gob.ve/webhooks/pagos',
        )

    def _crear_entrega_pendiente(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('10.00'), moneda_codigo='VES')
        evento = EventoOutbox.objects.create(pago=pago, event_type='pago.confirmado', payload={}, schema_version=1)
        return WebhookEntrega.objects.create(evento=evento)

    def test_entrega_exitosa_marca_entregado(self):
        entrega = self._crear_entrega_pendiente()
        publisher = Mock()
        publisher.entregar.return_value = 200

        resultado = WebhookRelayService.procesar_lote(publisher=publisher)

        entrega.refresh_from_db()
        self.assertEqual(resultado, {'entregados': 1, 'agotados': 0, 'reintentados': 0})
        self.assertEqual(entrega.estado, WebhookEntrega.Estado.ENTREGADO)
        self.assertEqual(entrega.intentos, 1)
        self.assertEqual(entrega.ultima_respuesta_status, 200)
        self.assertIsNotNone(entrega.ultimo_intento_at)
        publisher.entregar.assert_called_once_with(
            webhook_url='https://conatel.gob.ve/webhooks/pagos',
            webhook_secret=self.aplicacion.webhook_secret,
            event_id=entrega.evento.id, event_type='pago.confirmado', payload={}, schema_version=1,
        )

    def test_falla_incrementa_intentos_y_queda_pendiente(self):
        entrega = self._crear_entrega_pendiente()
        publisher = Mock()
        publisher.entregar.side_effect = WebhookEntregaFallidaError('status 500', status_code=500)

        resultado = WebhookRelayService.procesar_lote(publisher=publisher)

        entrega.refresh_from_db()
        self.assertEqual(resultado, {'entregados': 0, 'agotados': 0, 'reintentados': 1})
        self.assertEqual(entrega.estado, WebhookEntrega.Estado.PENDIENTE)
        self.assertEqual(entrega.intentos, 1)
        self.assertEqual(entrega.ultima_respuesta_status, 500)

    @override_settings(WEBHOOK_MAX_INTENTOS=3)
    def test_pasa_a_agotado_al_alcanzar_el_tope(self):
        entrega = self._crear_entrega_pendiente()
        publisher = Mock()
        publisher.entregar.side_effect = WebhookEntregaFallidaError('timeout')

        for _ in range(3):
            WebhookRelayService.procesar_lote(publisher=publisher)

        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, WebhookEntrega.Estado.AGOTADO)
        self.assertEqual(entrega.intentos, 3)
        self.assertEqual(publisher.entregar.call_count, 3)

    def test_no_reentrega_una_ya_entregada(self):
        entrega = self._crear_entrega_pendiente()
        publisher = Mock()
        publisher.entregar.return_value = 200
        WebhookRelayService.procesar_lote(publisher=publisher)

        resultado = WebhookRelayService.procesar_lote(publisher=publisher)

        self.assertEqual(resultado, {'entregados': 0, 'agotados': 0, 'reintentados': 0})
        publisher.entregar.assert_called_once()

    def test_respeta_el_limite_del_lote(self):
        for _ in range(3):
            self._crear_entrega_pendiente()
        publisher = Mock()
        publisher.entregar.return_value = 200

        resultado = WebhookRelayService.procesar_lote(publisher=publisher, limite=2)

        self.assertEqual(resultado['entregados'], 2)
        self.assertEqual(WebhookEntrega.objects.filter(estado=WebhookEntrega.Estado.PENDIENTE).count(), 1)
