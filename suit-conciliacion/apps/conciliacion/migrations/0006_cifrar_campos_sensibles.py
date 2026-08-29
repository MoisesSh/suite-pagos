from django.db import migrations
from fernet_fields import EncryptedCharField

from apps.shared.domain.fields import EncryptedJSONField

# Auditoría de seguridad (Bloque #16, PLAN-DE-MEJORAS.md): cedula_pagador,
# telefono_pagador y payload_crudo/payload viajaban en texto plano en la DB
# — cualquier dump/backup filtrado o el propio admin los exponía en claro.
# Patrón seguro (supervision-modelos-bd §6): agregar columnas temporales ya
# cifradas, hacer backfill vía RunPython (pasa por el ORM => cifra al
# guardar), recién ahí borrar las columnas viejas en claro y renombrar —
# nunca un AlterField directo de CharField/JSONField a un campo cifrado, que
# en Postgres intentaría un ALTER COLUMN TYPE bytea sin pasar los datos
# existentes por Fernet (quedarían corruptos, no cifrados).


def _backfill(apps, schema_editor):
    EventoPagoRecibido = apps.get_model('conciliacion', 'EventoPagoRecibido')
    ConsultaConciliacionProveedor = apps.get_model('conciliacion', 'ConsultaConciliacionProveedor')

    for evento in EventoPagoRecibido.objects.all():
        evento.payload_tmp = evento.payload
        evento.save(update_fields=['payload_tmp'])

    for consulta in ConsultaConciliacionProveedor.objects.all():
        consulta.telefono_pagador_tmp = consulta.telefono_pagador
        consulta.cedula_pagador_tmp = consulta.cedula_pagador
        consulta.payload_crudo_tmp = consulta.payload_crudo
        consulta.save(update_fields=['telefono_pagador_tmp', 'cedula_pagador_tmp', 'payload_crudo_tmp'])


def _backfill_reverso(apps, schema_editor):
    # Reversa: no hay forma de "descifrar hacia atrás" en texto plano de forma
    # segura para un rollback de esquema — las columnas *_tmp simplemente se
    # eliminan (RemoveField, más abajo en reverse_code implícito de AddField).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion', '0005_seed_banco_bdv'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventopagorecibido',
            name='payload_tmp',
            field=EncryptedJSONField(null=True),
        ),
        migrations.AddField(
            model_name='consultaconciliacionproveedor',
            name='telefono_pagador_tmp',
            field=EncryptedCharField(max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='consultaconciliacionproveedor',
            name='cedula_pagador_tmp',
            field=EncryptedCharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='consultaconciliacionproveedor',
            name='payload_crudo_tmp',
            field=EncryptedJSONField(null=True),
        ),
        migrations.RunPython(_backfill, _backfill_reverso),
        migrations.RemoveField(model_name='eventopagorecibido', name='payload'),
        migrations.RemoveField(model_name='consultaconciliacionproveedor', name='telefono_pagador'),
        migrations.RemoveField(model_name='consultaconciliacionproveedor', name='cedula_pagador'),
        migrations.RemoveField(model_name='consultaconciliacionproveedor', name='payload_crudo'),
        migrations.RenameField(model_name='eventopagorecibido', old_name='payload_tmp', new_name='payload'),
        migrations.RenameField(
            model_name='consultaconciliacionproveedor', old_name='telefono_pagador_tmp', new_name='telefono_pagador',
        ),
        migrations.RenameField(
            model_name='consultaconciliacionproveedor', old_name='cedula_pagador_tmp', new_name='cedula_pagador',
        ),
        migrations.RenameField(
            model_name='consultaconciliacionproveedor', old_name='payload_crudo_tmp', new_name='payload_crudo',
        ),
        migrations.AlterField(
            model_name='eventopagorecibido',
            name='payload',
            field=EncryptedJSONField(),
        ),
        migrations.AlterField(
            model_name='consultaconciliacionproveedor',
            name='telefono_pagador',
            field=EncryptedCharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='consultaconciliacionproveedor',
            name='cedula_pagador',
            field=EncryptedCharField(max_length=20, blank=True),
        ),
        migrations.AlterField(
            model_name='consultaconciliacionproveedor',
            name='payload_crudo',
            field=EncryptedJSONField(),
        ),
    ]
