from django.db import migrations

# db-plan-pagos.md sección 5, punto 3: VES es la única moneda con tráfico real
# hoy; USD queda reservado/inactivo, listo para habilitarse por dato (activo=True)
# sin migración de esquema nueva cuando haga falta.
MONEDAS = [
    {'codigo': 'VES', 'nombre': 'Bolívar', 'activo': True},
    {'codigo': 'USD', 'nombre': 'Dólar estadounidense', 'activo': False},
]


def poblar_monedas(apps, schema_editor):
    Moneda = apps.get_model('autorizacion', 'Moneda')
    for datos in MONEDAS:
        Moneda.objects.get_or_create(codigo=datos['codigo'], defaults=datos)


def revertir_monedas(apps, schema_editor):
    Moneda = apps.get_model('autorizacion', 'Moneda')
    Moneda.objects.filter(codigo__in=[m['codigo'] for m in MONEDAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('autorizacion', '0002_trigger_transicion_estado_pago'),
    ]

    operations = [
        migrations.RunPython(poblar_monedas, revertir_monedas),
    ]
