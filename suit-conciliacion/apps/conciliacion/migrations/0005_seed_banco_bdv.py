from django.db import migrations

# Catálogo mínimo para que ConsultaConciliacionProveedor/MovimientoBancario
# puedan resolver su FK de PROTECT a Banco en tiempo de ejecución. Reportado
# por suit-backend: un EventoOutbox real (banco_pagador_codigo='0102') caía
# en Discrepancia error_proveedor en vez de llegar al matching normal porque
# el catálogo Banco estaba vacío en la DB de Conciliación. Mismo patrón que
# suit-orquestador/apps/autorizacion/migrations/0004_seed_catalogos_bdv_c2p.py
# — cada servicio mantiene su propia copia local del catálogo, sin FK
# cruzada entre las DBs (db-plan-pagos.md §2.5).

BANCO_CODIGO = '0102'


def poblar_banco_bdv(apps, schema_editor):
    Banco = apps.get_model('conciliacion', 'Banco')
    Banco.objects.get_or_create(
        codigo=BANCO_CODIGO, defaults={'nombre': 'Banco de Venezuela', 'activo': True},
    )


def revertir_banco_bdv(apps, schema_editor):
    Banco = apps.get_model('conciliacion', 'Banco')
    Banco.objects.filter(codigo=BANCO_CODIGO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion', '0004_alter_consultaconciliacionproveedor_fecha_pago'),
    ]

    operations = [
        migrations.RunPython(poblar_banco_bdv, revertir_banco_bdv),
    ]
