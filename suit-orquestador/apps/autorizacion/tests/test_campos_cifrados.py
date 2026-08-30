import uuid
from decimal import Decimal

from cryptography.fernet import Fernet
from django.db import connection
from django.test import override_settings

from apps.autorizacion.application.services import FlujoCobroC2PService
from apps.autorizacion.domain.models import AplicacionRegistrada, EventoOutbox
from apps.autorizacion.tests.base import BaseAPITestCase

CLAVE_A = Fernet.generate_key().decode()
CLAVE_B = Fernet.generate_key().decode()


class EncryptedJSONFieldTests(BaseAPITestCase):
    """Hallazgo de seguridad #5: payload_crudo/EventoOutbox.payload/
    IdempotencyKey.response_snapshot traían cédula, teléfono y la respuesta
    completa de BDV en texto plano en Postgres."""

    def setUp(self):
        super().setUp()
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Test', app_origen_id=uuid.uuid4())

    def _crear_evento(self, payload):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('10.00'), moneda_codigo='VES')
        return EventoOutbox.objects.create(pago=pago, event_type='pago.confirmado', payload=payload, schema_version=1)

    def test_roundtrip_preserva_el_dict(self):
        payload = {'cedula_pagador': 'V12345678', 'telefono_pagador': '04121234567', 'monto': '10.00'}
        evento = self._crear_evento(payload)

        evento.refresh_from_db()

        self.assertEqual(evento.payload, payload)

    @override_settings(FIELD_ENCRYPTION_KEYS=CLAVE_A)
    def test_valor_persistido_en_la_db_no_es_texto_plano(self):
        payload = {'cedula_pagador': 'V12345678', 'telefono_pagador': '04121234567'}
        evento = self._crear_evento(payload)

        with connection.cursor() as cursor:
            cursor.execute('SELECT payload FROM autorizacion_eventooutbox WHERE id = %s', [str(evento.id)])
            valor_crudo = cursor.fetchone()[0]

        self.assertNotIn('V12345678', valor_crudo)
        self.assertNotIn('04121234567', valor_crudo)

    @override_settings(FIELD_ENCRYPTION_KEYS=f'{CLAVE_B},{CLAVE_A}')
    def test_lee_datos_cifrados_con_una_clave_vieja_tras_rotar(self):
        """MultiFernet: la PRIMERA clave cifra, TODAS se prueban al descifrar —
        una fila cifrada con una clave que ya no es la principal debe seguir
        siendo legible mientras esa clave siga en la lista."""
        with override_settings(FIELD_ENCRYPTION_KEYS=CLAVE_A):
            evento = self._crear_evento({'referencia_corta': '090037579602'})
            evento_id = evento.id

        # CLAVE_B ahora es la principal (cifra), CLAVE_A quedó como secundaria
        # (solo para poder seguir leyendo lo ya cifrado con ella).
        releido = EventoOutbox.objects.get(id=evento_id)
        self.assertEqual(releido.payload, {'referencia_corta': '090037579602'})
