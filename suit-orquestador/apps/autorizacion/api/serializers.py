from rest_framework import serializers


class ValidarAccesoRequestSerializer(serializers.Serializer):
    dominio = serializers.CharField(max_length=255)
    proveedor = serializers.CharField(max_length=30, help_text='Código de ProveedorPago (ej. BDV).')


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
    checkout_token = serializers.CharField(help_text='Emitido por ValidarAccesoView.')
    proveedor = serializers.CharField(max_length=30)
    idempotency_key = serializers.UUIDField()
    monto = serializers.DecimalField(max_digits=19, decimal_places=2)
    moneda = serializers.CharField(max_length=3)
    cedula_pagador = serializers.CharField(max_length=20)
    telefono_pagador = serializers.CharField(max_length=15)
    banco_codigo = serializers.CharField(max_length=4)
    concepto = serializers.CharField(max_length=100, required=False, default='Pago')
    otp = serializers.CharField(max_length=20)
