import unittest
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.conciliacion.domain.models import ConsultaConciliacionProveedor
from apps.shared.tests import factories


@unittest.skipUnless(
    connection.vendor == 'postgresql',
    'Este bug es específico del adaptador JSON de Postgres (psycopg envuelve '
    'JSONField.get_db_prep_save() en un objeto Jsonb(...), no un string — '
    'sqlite sí devuelve un string plano ahí, así que esconde el bug por '
    'completo). Encontrado en real: la primera versión de EncryptedJSONField '
    'pasaba ese wrapper por `force_bytes()`, que cae en `str(objeto)` — el '
    '__repr__ de Jsonb trunca el contenido a un preview corto para debug '
    '("Jsonb({...} ... (N chars))"), y ESO quedaba cifrado en vez del JSON '
    'real. Corrompió 2 filas reales en Docker antes de detectarse (sin '
    'recuperación posible — el preview es una vista truncada, no el dato).',
)
class CifradoCamposSensiblesTests(TestCase):
    def test_payload_de_evento_pago_recibido_redondea_exacto_y_no_queda_en_claro(self):
        payload_original = {
            'cedula_pagador': 'V12345678',
            'telefono_pagador': '04120000000',
            'anidado': {'lista': [1, 2, 3], 'texto': 'áéíóú ñ'},
        }
        evento = factories.crear_evento_pago(payload=payload_original)
        evento.refresh_from_db()

        self.assertEqual(evento.payload, payload_original)

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT payload FROM conciliacion_eventopagorecibido WHERE id = %s', [str(evento.id)],
            )
            crudo = bytes(cursor.fetchone()[0])
        self.assertNotIn(b'V12345678', crudo)
        self.assertNotIn(b'04120000000', crudo)

    def test_consulta_conciliacion_redondea_exacto_y_no_queda_en_claro(self):
        evento = factories.crear_evento_pago()
        banco = factories.crear_banco()
        payload_crudo = {'code': 1000, 'message': 'Monto: 120.00 - estatus: Transacción realizada'}

        consulta = ConsultaConciliacionProveedor.objects.create(
            evento=evento, banco=banco, referencia_corta='12345678',
            telefono_pagador='04127141363', cedula_pagador='V27037606',
            importe_esperado=Decimal('120.00'), fecha_pago=timezone.now().date(),
            codigo_respuesta_raw='1000', resultado_interpretado=ConsultaConciliacionProveedor.ResultadoInterpretado.CONCILIADO,
            payload_crudo=payload_crudo,
        )
        consulta.refresh_from_db()

        self.assertEqual(consulta.telefono_pagador, '04127141363')
        self.assertEqual(consulta.cedula_pagador, 'V27037606')
        self.assertEqual(consulta.payload_crudo, payload_crudo)

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT telefono_pagador, cedula_pagador, payload_crudo '
                'FROM conciliacion_consultaconciliacionproveedor WHERE id = %s',
                [str(consulta.id)],
            )
            telefono_crudo, cedula_crudo, payload_crudo_crudo = (bytes(v) for v in cursor.fetchone())
        self.assertNotIn(b'04127141363', telefono_crudo)
        self.assertNotIn(b'V27037606', cedula_crudo)
        self.assertNotIn(b'Transacci', payload_crudo_crudo)
