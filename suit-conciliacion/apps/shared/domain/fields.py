import json

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.db import models


def _fernet():
    claves = [c.strip() for c in settings.FIELD_ENCRYPTION_KEYS.split(',') if c.strip()]
    return MultiFernet([Fernet(clave.encode()) for clave in claves])


class EncryptedJSONField(models.TextField):
    """Réplica literal del campo de `suit-orquestador`
    (`apps/autorizacion/domain/campos_cifrados.py`) — mismo mecanismo,
    mismo setting `FIELD_ENCRYPTION_KEYS`, para que ambos servicios usen el
    mismo criterio de cifrado en reposo (auditoría de seguridad, Bloque
    #16). `TextField` como storage (no `BinaryField`/JSONField compuesto):
    evita el bug real encontrado en la primera versión de este campo, donde
    `JSONField.get_db_prep_save()` en Postgres devuelve un wrapper
    `psycopg.types.json.Jsonb(...)` en vez de un string, y terminaba
    cifrándose su `repr()` truncado en vez del JSON real."""

    def get_prep_value(self, value):
        if value is None:
            return None
        crudo = json.dumps(value).encode('utf-8')
        return _fernet().encrypt(crudo).decode('ascii')

    def from_db_value(self, value, expression, connection):
        return self._descifrar(value)

    def to_python(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        return self._descifrar(value)

    def _descifrar(self, value):
        if value is None:
            return None
        crudo = _fernet().decrypt(value.encode('ascii'))
        return json.loads(crudo.decode('utf-8'))


class EncryptedCharField(models.TextField):
    """Mismo mecanismo que `EncryptedJSONField`, para valores de texto plano
    (`telefono_pagador`/`cedula_pagador`) — suit-orquestador no tiene campos
    de este tipo cifrados, así que no hay un original que replicar literal;
    sigue el mismo patrón (MultiFernet, `FIELD_ENCRYPTION_KEYS`) para no
    introducir un segundo mecanismo de cifrado en el proyecto."""

    def get_prep_value(self, value):
        if value is None:
            return None
        return _fernet().encrypt(value.encode('utf-8')).decode('ascii')

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return _fernet().decrypt(value.encode('ascii')).decode('utf-8')
