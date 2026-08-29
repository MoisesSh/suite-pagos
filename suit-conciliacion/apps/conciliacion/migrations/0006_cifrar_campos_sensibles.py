from django.db import migrations

from apps.shared.domain.fields import EncryptedCharField, EncryptedJSONField

# Auditoría de seguridad (Bloque #16, PLAN-DE-MEJORAS.md): cedula_pagador,
# telefono_pagador y payload_crudo/payload viajaban en texto plano en la DB
# — cualquier dump/backup filtrado o el propio admin los exponía en claro.
# Patrón seguro (supervision-modelos-bd §6): agregar columnas temporales ya
# cifradas, hacer backfill vía RunPython (pasa por el ORM => cifra al
# guardar), recién ahí borrar las columnas viejas en claro y renombrar —
# nunca un AlterField directo de CharField/JSONField a un campo cifrado, que
# en Postgres castearía el valor existente a texto plano sin pasarlo por
# Fernet (quedaría corrupto, no cifrado — encontrado en real, ver commit
# cb38141 y el aviso de suit-backend sobre el mismo riesgo en su lado).
#
# Campo cifrado: EncryptedCharField/EncryptedJSONField de
# apps/shared/domain/fields.py (TextField + MultiFernet, mismo mecanismo y
# setting FIELD_ENCRYPTION_KEYS que suit-orquestador) — reemplaza la primera
# versión de este archivo (django-fernet-fields-v2, BinaryField), que
# funcionaba en sqlite pero corrompía JSON en Postgres real (el wrapper
# psycopg.types.json.Jsonb(...) de JSONField.get_db_prep_save() se cifraba
# vía su __repr__ truncado, no el JSON completo).


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
            field=EncryptedCharField(null=True),
        ),
        migrations.AddField(
            model_name='consultaconciliacionproveedor',
            name='cedula_pagador_tmp',
            field=EncryptedCharField(null=True, blank=True),
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
            field=EncryptedCharField(),
        ),
        migrations.AlterField(
            model_name='consultaconciliacionproveedor',
            name='cedula_pagador',
            field=EncryptedCharField(blank=True),
        ),
        migrations.AlterField(
            model_name='consultaconciliacionproveedor',
            name='payload_crudo',
            field=EncryptedJSONField(),
        ),
    ]
