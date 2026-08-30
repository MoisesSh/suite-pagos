import hashlib
import hmac
import json

import requests
from django.conf import settings


class WebhookEntregaFallidaError(Exception):
    """El webhook no respondió 2xx, o no respondió en absoluto (timeout/conexión).
    La fila de WebhookEntrega debe seguir en pendiente/agotado, nunca marcarse
    entregado ante esta excepción."""

    def __init__(self, detalle, status_code=None):
        self.status_code = status_code
        super().__init__(detalle)


class WebhookPublisher:
    """Entrega un EventoOutbox al webhook_url de la app consumidora, firmado con
    HMAC-SHA256 (header `X-Suit-Signature: sha256=<hex>`, mismo esquema que
    Stripe/PayPal/Mercado Pago) sobre el body exacto enviado — la app consumidora
    debe validar la firma antes de confiar en el payload. Timeout corto: nunca
    bloquear el poller esperando a un consumidor lento."""

    def __init__(self, timeout=None):
        self._timeout = timeout or settings.WEBHOOK_TIMEOUT_SEGUNDOS

    def entregar(self, *, webhook_url, webhook_secret, event_id, event_type, payload, schema_version):
        envelope = {
            'event_id': str(event_id),
            'event_type': event_type,
            'schema_version': schema_version,
            'payload': payload,
        }
        # Serializado una sola vez: la firma se calcula sobre los bytes EXACTOS
        # que se envían — si el receptor re-serializara distinto antes de
        # comparar, la validación fallaría aunque el contenido sea "igual".
        cuerpo = json.dumps(envelope, separators=(',', ':')).encode('utf-8')
        firma = hmac.new(webhook_secret.encode('utf-8'), cuerpo, hashlib.sha256).hexdigest()

        try:
            respuesta = requests.post(
                webhook_url,
                data=cuerpo,
                headers={'Content-Type': 'application/json', 'X-Suit-Signature': f'sha256={firma}'},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise WebhookEntregaFallidaError(str(exc)) from exc

        if not (200 <= respuesta.status_code < 300):
            raise WebhookEntregaFallidaError(f'status {respuesta.status_code}', status_code=respuesta.status_code)

        return respuesta.status_code
