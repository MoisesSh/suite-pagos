from rest_framework import serializers


class MensajeRespuestaSerializer(serializers.Serializer):
    """Serializer compartido para respuestas de error/mensaje simples (403/404/409/503)."""

    error = serializers.CharField(required=False)
    mensaje = serializers.CharField(required=False)
