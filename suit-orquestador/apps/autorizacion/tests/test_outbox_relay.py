import uuid
from decimal import Decimal
from unittest.mock import Mock

from django.test import override_settings

from apps.autorizacion.application.services import FlujoCobroC2PService
from apps.autorizacion.application.services.outbox_relay import OutboxRelayService
from apps.autorizacion.domain.models import AplicacionRegistrada, EventoOutbox
from apps.autorizacion.infrastructure.rabbitmq_publisher import PublicacionNoConfirmadaError
from apps.autorizacion.tests.base import BaseAPITestCase


class OutboxRelayServiceTests(BaseAPITestCase):
    """Mockea RabbitMQOutboxPublisher — la conexión real a RabbitMQ se valida por
    fuera del test suite (verificación manual contra el contenedor real, ver
    resumen del Bloque #6), no en tests automáticos que deban correr sin broker."""

    def setUp(self):
        super().setUp()
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())

    def _crear_evento_pendiente(self, event_type='pago.confirmado'):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')
        return EventoOutbox.objects.create(
            pago=pago, event_type=event_type, payload={'pago_id': str(pago.id)}, schema_version=1,
        )

    def test_publica_evento_pendiente_y_lo_marca_enviado(self):
        evento = self._crear_evento_pendiente()
        publisher = Mock()

        resultado = OutboxRelayService.procesar_lote(publisher=publisher)

        evento.refresh_from_db()
        self.assertEqual(resultado, {'enviados': 1, 'fallidos': 0, 'reintentados': 0})
        self.assertEqual(evento.estado, EventoOutbox.Estado.ENVIADO)
        self.assertIsNotNone(evento.sent_at)
        publisher.publicar.assert_called_once_with(
            event_id=evento.id, event_type='pago.confirmado', payload=evento.payload, schema_version=1,
        )

    def test_no_marca_enviado_si_el_publisher_no_confirma(self):
        evento = self._crear_evento_pendiente()
        publisher = Mock()
        publisher.publicar.side_effect = PublicacionNoConfirmadaError('nack')

        resultado = OutboxRelayService.procesar_lote(publisher=publisher)

        evento.refresh_from_db()
        self.assertEqual(resultado, {'enviados': 0, 'fallidos': 0, 'reintentados': 1})
        self.assertEqual(evento.estado, EventoOutbox.Estado.PENDIENTE)
        self.assertEqual(evento.intentos, 1)
        self.assertIsNotNone(evento.ultimo_intento_at)

    @override_settings(OUTBOX_RELAY_MAX_INTENTOS=3)
    def test_pasa_a_fallido_al_agotar_los_intentos(self):
        evento = self._crear_evento_pendiente()
        publisher = Mock()
        publisher.publicar.side_effect = PublicacionNoConfirmadaError('nack')

        for _ in range(3):
            OutboxRelayService.procesar_lote(publisher=publisher)

        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoOutbox.Estado.FALLIDO)
        self.assertEqual(evento.intentos, 3)
        self.assertEqual(publisher.publicar.call_count, 3)

    def test_no_vuelve_a_publicar_un_evento_ya_enviado(self):
        evento = self._crear_evento_pendiente()
        publisher = Mock()
        OutboxRelayService.procesar_lote(publisher=publisher)

        resultado = OutboxRelayService.procesar_lote(publisher=publisher)

        self.assertEqual(resultado, {'enviados': 0, 'fallidos': 0, 'reintentados': 0})
        publisher.publicar.assert_called_once()

    def test_respeta_el_limite_del_lote(self):
        for _ in range(3):
            self._crear_evento_pendiente()
        publisher = Mock()

        resultado = OutboxRelayService.procesar_lote(publisher=publisher, limite=2)

        self.assertEqual(resultado['enviados'], 2)
        self.assertEqual(EventoOutbox.objects.filter(estado=EventoOutbox.Estado.PENDIENTE).count(), 1)
