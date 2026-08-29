import json

from django.db import models
from django.utils.encoding import force_bytes, force_str
from fernet_fields import EncryptedField


class EncryptedJSONField(EncryptedField, models.JSONField):
    """`JSONField` cifrado con Fernet (mismo mecanismo que `EncryptedCharField`/
    `EncryptedTextField` de `django-fernet-fields-v2`, que no trae una variante
    para JSON — se compone igual que sus propios campos:
    `class EncryptedTextField(EncryptedField, models.TextField): pass`).

    Serializa/deserializa JSON explícitamente en vez de delegar en
    `super().get_db_prep_save()`/`from_db_value()` de `JSONField`: en
    Postgres, `JSONField.get_db_prep_save()` devuelve un wrapper
    `psycopg.types.json.Jsonb(...)` (pensado para que el driver lo serialice
    él mismo al ejecutar la query), no un string — `EncryptedField` lo cifra
    igual, vía `force_bytes()`, que sobre un objeto no-string cae en
    `str(obj).encode()` — el resultado cifrado es el repr de Python del
    wrapper (`"Jsonb({...})"`), no JSON válido. En sqlite no se nota (ahí
    `JSONField` sí devuelve un string plano), lo cual esconde el bug si solo
    se prueba localmente sin Postgres real."""

    def get_db_prep_save(self, value, connection):
        if value is None:
            return value
        serializado = json.dumps(value, cls=self.encoder)
        cifrado = self.fernet.encrypt(force_bytes(serializado))
        return connection.Database.Binary(cifrado)

    def from_db_value(self, value, expression, connection, *args):
        if value is None:
            return value
        descifrado = self.fernet.decrypt(bytes(value))
        return json.loads(force_str(descifrado), cls=self.decoder)
