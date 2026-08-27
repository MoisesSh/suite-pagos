import uuid

from apps.autorizacion.application.services import IdempotencyConflictError, IdempotencyService
from apps.autorizacion.domain.models import IdempotencyKey
from apps.autorizacion.tests.base import BaseAPITestCase


class IdempotencyServiceTests(BaseAPITestCase):
    def test_primera_vez_crea_pendiente(self):
        key = uuid.uuid4()
        idem, creada = IdempotencyService.obtener_o_crear(key, {'monto': '100.00'})

        self.assertTrue(creada)
        self.assertEqual(idem.estado, IdempotencyKey.Estado.PENDIENTE)

    def test_misma_key_mismo_payload_no_crea_de_nuevo(self):
        key = uuid.uuid4()
        payload = {'monto': '100.00', 'moneda': 'VES'}
        idem1, creada1 = IdempotencyService.obtener_o_crear(key, payload)
        idem2, creada2 = IdempotencyService.obtener_o_crear(key, payload)

        self.assertTrue(creada1)
        self.assertFalse(creada2)
        self.assertEqual(idem1.id, idem2.id)

    def test_misma_key_payload_distinto_lanza_conflicto(self):
        key = uuid.uuid4()
        IdempotencyService.obtener_o_crear(key, {'monto': '100.00'})

        with self.assertRaises(IdempotencyConflictError):
            IdempotencyService.obtener_o_crear(key, {'monto': '200.00'})

    def test_finalizar_guarda_estado_y_snapshot(self):
        idem, _ = IdempotencyService.obtener_o_crear(uuid.uuid4(), {'monto': '100.00'})

        IdempotencyService.finalizar(
            idem, estado=IdempotencyKey.Estado.COMPLETADO, status_code=200, body={'pago_id': 'abc'},
        )

        idem.refresh_from_db()
        self.assertEqual(idem.estado, IdempotencyKey.Estado.COMPLETADO)
        self.assertEqual(idem.response_snapshot, {'status_code': 200, 'body': {'pago_id': 'abc'}})
