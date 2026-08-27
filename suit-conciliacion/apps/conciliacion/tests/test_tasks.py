import uuid
from unittest.mock import patch

from django.test import TestCase

from apps.conciliacion.domain.models import (
    ConsultaConciliacionProveedor,
    Discrepancia,
    EventoPagoRecibido,
)
from apps.conciliacion.infrastructure.bdv_conciliacion_client import BdvConciliacionClient
from apps.conciliacion.infrastructure.tasks import consumir_evento_pago
from apps.shared.tests import factories


def _envelope_pago_confirmado(**overrides):
    payload = {
        'pago_id': str(uuid.uuid4()),
        'aplicacion_id': str(uuid.uuid4()),
        'proveedor_codigo': 'BDV',
        'medio_pago_codigo': 'C2P',
        'monto': '120.00',
        'moneda_codigo': 'VES',
        'cedula_pagador': 'V27037606',
        'telefono_pagador': '04127141363',
        'banco_pagador_codigo': '0102',
        'telefono_comercio': '04140282647',
        'referencia_corta': '12345678',
        'identificador_interbancario': '0' * 62,
        'codigo_respuesta_proveedor': '1000',
        'fecha_pago': '2026-08-27',
        'capturado_at': '2026-08-27T18:42:10.123456+00:00',
        'estado': 'capturado',
        'routing_flag': 'legacy',
        'payload_crudo_captura': {},
    }
    payload.update(overrides.pop('payload', {}))
    envelope = {
        'event_id': str(uuid.uuid4()),
        'event_type': 'pago.confirmado',
        'payload': payload,
        'schema_version': 1,
    }
    envelope.update(overrides)
    return envelope


class ConsumirEventoPagoTests(TestCase):
    def test_evento_no_pago_confirmado_solo_se_registra_y_marca_procesado(self):
        envelope = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'pago.reembolsado',
            'payload': {'algo': 'irrelevante'},
            'schema_version': 1,
        }

        consumir_evento_pago(envelope)

        evento = EventoPagoRecibido.objects.get(event_id=envelope['event_id'])
        self.assertIsNotNone(evento.procesado_at)

    def test_evento_ya_procesado_no_se_reprocesa(self):
        evento = factories.crear_evento_pago(event_type='pago.reembolsado')
        from apps.conciliacion.application.services.ingesta import IngestaService
        IngestaService.marcar_procesado(evento)

        envelope = {
            'event_id': str(evento.event_id),
            'event_type': evento.event_type,
            'payload': evento.payload,
            'schema_version': evento.schema_version,
        }

        with patch.object(BdvConciliacionClient, 'consultar_movimiento') as mock_consultar:
            consumir_evento_pago(envelope)

        mock_consultar.assert_not_called()

    @patch.object(BdvConciliacionClient, 'consultar_movimiento')
    def test_pago_confirmado_llama_bdv_y_registra_consulta(self, mock_consultar):
        factories.crear_banco(codigo='0102', nombre='Banco de Venezuela')
        mock_consultar.return_value = {
            'code': 1000,
            'message': 'Monto: 120.00 - estatus: Transacción realizada',
            'data': {'status': '1000', 'amount': '120.00', 'reason': 'Transacción realizada', 'referencia': '12345678'},
            'status': 200,
        }
        envelope = _envelope_pago_confirmado()

        consumir_evento_pago(envelope)

        mock_consultar.assert_called_once_with(
            cedula_pagador='V27037606',
            telefono_pagador='04127141363',
            telefono_destino='04140282647',
            referencia_corta='12345678',
            fecha_pago='2026-08-27',
            importe='120.00',
            banco_origen_codigo='0102',
        )
        evento = EventoPagoRecibido.objects.get(event_id=envelope['event_id'])
        self.assertIsNotNone(evento.procesado_at)
        consulta = ConsultaConciliacionProveedor.objects.get(evento=evento)
        self.assertEqual(consulta.resultado_interpretado, ConsultaConciliacionProveedor.ResultadoInterpretado.CONCILIADO)
        self.assertFalse(Discrepancia.objects.filter(evento=evento).exists())

    @patch.object(BdvConciliacionClient, 'consultar_movimiento')
    def test_pago_confirmado_banco_no_catalogado_genera_discrepancia_sin_llamar_bdv(self, mock_consultar):
        envelope = _envelope_pago_confirmado(payload={'banco_pagador_codigo': '9999'})

        consumir_evento_pago(envelope)

        mock_consultar.assert_not_called()
        evento = EventoPagoRecibido.objects.get(event_id=envelope['event_id'])
        self.assertIsNotNone(evento.procesado_at)
        discrepancia = Discrepancia.objects.get(evento=evento)
        self.assertEqual(discrepancia.tipo, Discrepancia.Tipo.ERROR_PROVEEDOR)
        self.assertEqual(discrepancia.severidad, Discrepancia.Severidad.CRITICA)

    @patch.object(BdvConciliacionClient, 'consultar_movimiento')
    def test_bdv_no_disponible_deja_evento_sin_marcar_para_reintento_de_celery(self, mock_consultar):
        from apps.conciliacion.infrastructure.bdv_conciliacion_client import BdvConciliacionNoDisponible

        factories.crear_banco(codigo='0102', nombre='Banco de Venezuela')
        mock_consultar.side_effect = BdvConciliacionNoDisponible('timeout')
        envelope = _envelope_pago_confirmado()

        with self.assertRaises(BdvConciliacionNoDisponible):
            consumir_evento_pago(envelope)

        evento = EventoPagoRecibido.objects.get(event_id=envelope['event_id'])
        self.assertIsNone(evento.procesado_at)
