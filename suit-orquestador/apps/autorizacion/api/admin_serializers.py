from rest_framework import serializers

from apps.autorizacion.domain.models import AplicacionProveedorPermitido, AplicacionRegistrada, DominioPermitido


class AdminAplicacionCrearSerializer(serializers.Serializer):
    """Mismo shape que `CreateAplicacionParams` de suit-portal — para que su repo
    real reemplace al mock sin tocar application/ ni ui/ del lado del portal."""
    nombre = serializers.CharField(max_length=150)
    dominio = serializers.CharField(max_length=255)
    proveedor = serializers.CharField(max_length=30, help_text='Código de ProveedorPago (ej. BDV).')
    app_origen_id = serializers.UUIDField(
        required=False, allow_null=True,
        help_text='Id de AppConsumidora en el Developer Portal. Si no se envía, el Orquestador genera uno propio.',
    )


class AdminAplicacionSerializer(serializers.Serializer):
    """Respuesta de creación — mismo shape que `AplicacionRegistradaEntity` de suit-portal."""
    id = serializers.UUIDField()
    nombre = serializers.CharField()
    dominio = serializers.CharField()
    proveedor = serializers.CharField()


class DominioPermitidoInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DominioPermitido
        fields = ['id', 'dominio', 'activo']


class AplicacionProveedorPermitidoInlineSerializer(serializers.ModelSerializer):
    proveedor = serializers.CharField(source='proveedor.codigo')

    class Meta:
        model = AplicacionProveedorPermitido
        fields = ['id', 'proveedor', 'activo', 'autorizado_en']


class AdminAplicacionListItemSerializer(serializers.ModelSerializer):
    dominios = DominioPermitidoInlineSerializer(many=True, read_only=True)
    proveedores_autorizados = AplicacionProveedorPermitidoInlineSerializer(many=True, read_only=True)

    class Meta:
        model = AplicacionRegistrada
        fields = ['id', 'nombre', 'app_origen_id', 'activa', 'created_at', 'dominios', 'proveedores_autorizados']


class AdminAplicacionActivarSerializer(serializers.ModelSerializer):
    class Meta:
        model = AplicacionRegistrada
        fields = ['activa']
