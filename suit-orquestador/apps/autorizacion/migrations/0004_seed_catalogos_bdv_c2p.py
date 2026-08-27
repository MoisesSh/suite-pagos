from django.db import migrations

# Catálogos mínimos para que el adaptador BDV Pago Móvil C2P (Bloque #3) pueda
# resolver sus FK de PROTECT en tiempo de ejecución. Fuente: `Doc - API C2P
# Cuentas Múltiples.pdf` (tabla de errores) y research-brief-pagos.md 4.1.

MEDIO_PAGO_CODIGO = 'C2P'
PROVEEDOR_CODIGO = 'BDV'
BANCO_CODIGO = '0102'
TIPO_OPERACION_CODIGO = 'CELE'

# categoria: 'exito' | 'duplicado_idempotente' | 'error_negocio' | 'error_tecnico'
# 1026/1094 -> duplicado_idempotente (señal nativa de idempotencia del banco, no error real).
# 1002/1041/1050/1091 -> error_tecnico (falla de conector/servicio/timeout/banco destino
# inactivo, ninguno atribuible a un dato inválido del pagador/comercio).
# Resto -> error_negocio (datos inválidos, saldo, límites, afiliación).
CODIGOS_RESPUESTA = [
    ('1000', 'Transacción realizada', 'exito'),
    ('1002', 'Ha ocurrido un error envío conector', 'error_tecnico'),
    ('1006', 'El Rif suministrado no es Merchant', 'error_negocio'),
    ('1013', 'Monto inválido', 'error_negocio'),
    ('1014', 'Beneficiario no afiliado a PagomóvilBDV', 'error_negocio'),
    ('1015', 'No afiliado a ClavemóvilBDV', 'error_negocio'),
    ('1026', 'Referencia / Monto duplicado', 'duplicado_idempotente'),
    ('1034', 'Saldo insuficiente', 'error_negocio'),
    ('1041', 'Servicio inactivo', 'error_tecnico'),
    ('1050', 'La solicitud superó el Timeout', 'error_tecnico'),
    ('1055', 'Clave no existe', 'error_negocio'),
    ('1056', 'El número de teléfono no corresponde con el titular', 'error_negocio'),
    ('1061', 'Monto supera el límite diario', 'error_negocio'),
    ('1062', 'Cuenta con inconvenientes', 'error_negocio'),
    ('1065', 'Cantidad de transacciones superada', 'error_negocio'),
    ('1080', 'Documento de identidad inválido', 'error_negocio'),
    ('1091', 'Banco destino inactivo', 'error_tecnico'),
    ('1092', 'Banco destino no afiliado', 'error_negocio'),
    ('1094', 'Operación duplicada', 'duplicado_idempotente'),
]


def poblar_catalogos_bdv(apps, schema_editor):
    MedioPago = apps.get_model('autorizacion', 'MedioPago')
    ProveedorPago = apps.get_model('autorizacion', 'ProveedorPago')
    Banco = apps.get_model('autorizacion', 'Banco')
    TipoOperacionProveedor = apps.get_model('autorizacion', 'TipoOperacionProveedor')
    CodigoRespuestaProveedor = apps.get_model('autorizacion', 'CodigoRespuestaProveedor')

    medio_pago, _ = MedioPago.objects.get_or_create(
        codigo=MEDIO_PAGO_CODIGO, defaults={'nombre': 'Pago Móvil C2P', 'activo': True},
    )
    proveedor, _ = ProveedorPago.objects.get_or_create(
        codigo=PROVEEDOR_CODIGO,
        defaults={'medio_pago': medio_pago, 'nombre': 'Banco de Venezuela', 'activo': True},
    )
    Banco.objects.get_or_create(
        codigo=BANCO_CODIGO, defaults={'nombre': 'Banco de Venezuela', 'activo': True},
    )
    TipoOperacionProveedor.objects.get_or_create(
        proveedor=proveedor, codigo=TIPO_OPERACION_CODIGO, defaults={'nombre': 'Pago Móvil C2P'},
    )
    for codigo, descripcion, categoria in CODIGOS_RESPUESTA:
        CodigoRespuestaProveedor.objects.get_or_create(
            proveedor=proveedor, codigo=codigo,
            defaults={'descripcion': descripcion, 'categoria': categoria},
        )


def revertir_catalogos_bdv(apps, schema_editor):
    ProveedorPago = apps.get_model('autorizacion', 'ProveedorPago')
    MedioPago = apps.get_model('autorizacion', 'MedioPago')
    Banco = apps.get_model('autorizacion', 'Banco')
    TipoOperacionProveedor = apps.get_model('autorizacion', 'TipoOperacionProveedor')
    CodigoRespuestaProveedor = apps.get_model('autorizacion', 'CodigoRespuestaProveedor')

    proveedor = ProveedorPago.objects.filter(codigo=PROVEEDOR_CODIGO).first()
    if proveedor:
        # PROTECT desde TipoOperacionProveedor/CodigoRespuestaProveedor: borrar hijas primero.
        CodigoRespuestaProveedor.objects.filter(proveedor=proveedor).delete()
        TipoOperacionProveedor.objects.filter(proveedor=proveedor).delete()
        proveedor.delete()
    MedioPago.objects.filter(codigo=MEDIO_PAGO_CODIGO).delete()
    Banco.objects.filter(codigo=BANCO_CODIGO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('autorizacion', '0003_seed_moneda'),
    ]

    operations = [
        migrations.RunPython(poblar_catalogos_bdv, revertir_catalogos_bdv),
    ]
