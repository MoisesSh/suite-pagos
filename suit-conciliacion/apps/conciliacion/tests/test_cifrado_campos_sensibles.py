from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.conciliacion.domain.models import ConsultaConciliacionProveedor
from apps.shared.tests import factories

# Nota histórica: la primera versión de este campo (django-fernet-fields-v2,
# BinaryField compuesto con JSONField) funcionaba en sqlite pero corrompía
# datos en Postgres real — JSONField.get_db_prep_save() ahí devuelve un
# wrapper psycopg.types.json.Jsonb(...), no un string, y se cifraba su
# __repr__ truncado en vez del JSON completo. El campo actual
# (apps/shared/domain/fields.py, TextField + MultiFernet, serialización JSON
# explícita) no depende de ningún adaptador de backend, así que este test ya
# no necesita restringirse a Postgres — corre igual en sqlite.


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
            crudo = cursor.fetchone()[0]
        self.assertNotIn('V12345678', crudo)
        self.assertNotIn('04120000000', crudo)

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
            telefono_crudo, cedula_crudo, payload_crudo_crudo = cursor.fetchone()
        self.assertNotIn('04127141363', telefono_crudo)
        self.assertNotIn('V27037606', cedula_crudo)
        self.assertNotIn('Transacci', payload_crudo_crudo)
