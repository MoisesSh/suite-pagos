from django.db import migrations

# Bloque #21 (PLAN-DE-MEJORAS.md): plan de cuentas definido por el usuario para
# el asiento de un cobro conciliado. Conatel es destinatario final del dinero
# (no una liquidación pendiente hacia la app afiliada) — una sola cuenta
# genérica de terceros para todos los pagadores, sin trazabilidad contable por
# pagador individual (esa identidad ya vive en ConsultaConciliacionProveedor).
# Mismo patrón que 0005_seed_banco_bdv.py. Códigos sin convención numérica
# establecida todavía — simples y legibles.

CUENTAS = [
    {'codigo': 'CXC-TERCEROS', 'nombre': 'Cuentas por Cobrar a Terceros'},
    {'codigo': 'ING-COBRO-TERCEROS', 'nombre': 'Ingresos por Cobro de Terceros'},
]


def poblar_cuentas_ledger(apps, schema_editor):
    CuentaContable = apps.get_model('conciliacion', 'CuentaContable')
    for cuenta in CUENTAS:
        CuentaContable.objects.get_or_create(
            codigo=cuenta['codigo'], defaults={'nombre': cuenta['nombre'], 'activa': True},
        )


def revertir_cuentas_ledger(apps, schema_editor):
    CuentaContable = apps.get_model('conciliacion', 'CuentaContable')
    CuentaContable.objects.filter(codigo__in=[c['codigo'] for c in CUENTAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion', '0007_transaccionledger_aplicacion_id'),
    ]

    operations = [
        migrations.RunPython(poblar_cuentas_ledger, revertir_cuentas_ledger),
    ]
