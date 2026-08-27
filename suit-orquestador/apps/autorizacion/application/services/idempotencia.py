import hashlib
import json

from apps.autorizacion.domain.models import IdempotencyKey


class IdempotencyConflictError(Exception):
    """Misma key con request_hash distinto — db-plan-pagos.md 2.3: nunca reusar la
    respuesta cacheada en ese caso, rechazar."""


def calcular_hash(payload_canonico):
    canonico = json.dumps(payload_canonico, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonico.encode()).hexdigest()


class IdempotencyService:
    @staticmethod
    def obtener_o_crear(key, payload_canonico):
        request_hash = calcular_hash(payload_canonico)
        idem, creada = IdempotencyKey.objects.get_or_create(key=key, defaults={'request_hash': request_hash})
        if not creada and idem.request_hash != request_hash:
            raise IdempotencyConflictError('request_hash_no_coincide')
        return idem, creada

    @staticmethod
    def finalizar(idem, *, estado, status_code, body):
        idem.estado = estado
        idem.response_snapshot = {'status_code': status_code, 'body': body}
        idem.save(update_fields=['estado', 'response_snapshot', 'updated_at'])
