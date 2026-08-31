import uuid

from django.db import migrations, models

# Bloque #20 (PLAN-DE-MEJORAS.md): trazabilidad de la app consumidora dueña de
# cada transacción del ledger. Sin FK real (database-per-service, ver el
# comentario en el modelo). Tabla vacía en producción hoy (MatchingService
# nunca invoca LedgerService.registrar_transaccion todavía) — el default de
# esta migración solo existe para satisfacer el AddField no-nulleable si
# llegara a haber filas preexistentes en algún entorno; el modelo no lo trae.


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion', '0006_cifrar_campos_sensibles'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaccionledger',
            name='aplicacion_id',
            field=models.UUIDField(db_index=True, default=uuid.UUID('00000000-0000-0000-0000-000000000000')),
            preserve_default=False,
        ),
    ]
