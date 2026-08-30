import json

from cryptography.fernet import MultiFernet
from django.conf import settings
from django.db import models


class EncryptedJSONField(models.TextField):
    """JSONField cifrado en reposo (hallazgo de seguridad — payload_crudo/
    EventoOutbox.payload/IdempotencyKey.response_snapshot traían cédula,
    teléfono y la respuesta completa del banco en texto plano, sin ningún
    mecanismo de cifrado de campo).

    Fernet vía `cryptography` (ya en el ecosistema estándar, no un paquete
    Django de terceros sin mantenimiento como django-cryptography/
    django-fernet-fields, ambos abandonados desde ~2021). `MultiFernet`
    permite rotar: `FIELD_ENCRYPTION_KEYS` es una lista coma-separada de
    claves Fernet — la PRIMERA cifra en cada escritura nueva, TODAS se
    prueban al descifrar (así una fila cifrada con una clave vieja sigue
    siendo legible hasta que se vuelve a guardar con la clave actual).

    Fernet ya produce texto base64 URL-safe, por eso el storage es
    `TextField` (no `BinaryField`) — más simple con psycopg, sin manejo de
    `bytea`. No usar `.filter()`/lookups de contenido sobre este campo: el
    valor persistido es el token cifrado, no el JSON — ningún lookup de
    JSONField (`__contains`, acceso a key, etc.) tiene sentido acá."""

    def _fernet(self):
        claves = [c.strip() for c in settings.FIELD_ENCRYPTION_KEYS.split(',') if c.strip()]
        from cryptography.fernet import Fernet
        return MultiFernet([Fernet(clave.encode()) for clave in claves])

    def get_prep_value(self, value):
        if value is None:
            return None
        crudo = json.dumps(value).encode('utf-8')
        return self._fernet().encrypt(crudo).decode('ascii')

    def from_db_value(self, value, expression, connection):
        return self._descifrar(value)

    def to_python(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        return self._descifrar(value)

    def _descifrar(self, value):
        if value is None:
            return None
        crudo = self._fernet().decrypt(value.encode('ascii'))
        return json.loads(crudo.decode('utf-8'))
