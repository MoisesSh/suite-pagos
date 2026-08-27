from rest_framework import serializers


class ValidarAccesoRequestSerializer(serializers.Serializer):
    dominio = serializers.CharField(max_length=255)
    proveedor = serializers.CharField(max_length=30, help_text='Código de ProveedorPago (ej. BDV).')
    # La app consumidora ya sabe cuánto factura al iniciar el checkout — estos
    # valores quedan atados al checkout_token (CheckoutTokenService), nunca se
    # vuelven a aceptar desde el body de /cobro/ (ver EjecutarCobroRequestSerializer).
    monto = serializers.DecimalField(max_digits=19, decimal_places=2)
    moneda = serializers.CharField(max_length=3)
    concepto = serializers.CharField(max_length=100, required=False, default='Pago')


class AccesoAutorizadoSerializer(serializers.Serializer):
    autorizado = serializers.BooleanField()
    aplicacion = serializers.CharField()


class AccesoRechazadoSerializer(serializers.Serializer):
    autorizado = serializers.BooleanField()
    motivo = serializers.CharField()


class SolicitarOtpRequestSerializer(serializers.Serializer):
    checkout_token = serializers.CharField(help_text='Emitido por ValidarAccesoView.')
    proveedor = serializers.CharField(max_length=30)
    cedula_pagador = serializers.CharField(max_length=20)


class EjecutarCobroRequestSerializer(serializers.Serializer):
    """Sin monto/moneda/concepto: se leen del checkout_token verificado, nunca del
    body — el OTP autentica al pagador, no valida que el monto sea el que la app
    realmente factura. Aceptarlos acá sería un vector de fraude (un pagador
    técnico podría editar el monto del request y bajarse su propia factura)."""
    checkout_token = serializers.CharField(help_text='Emitido por ValidarAccesoView.')
    proveedor = serializers.CharField(max_length=30)
    idempotency_key = serializers.UUIDField()
    cedula_pagador = serializers.CharField(max_length=20)
    telefono_pagador = serializers.CharField(max_length=15)
    banco_codigo = serializers.CharField(max_length=4)
    otp = serializers.CharField(max_length=20)
