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
