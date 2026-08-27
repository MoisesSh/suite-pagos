from rest_framework import serializers

from apps.conciliacion.domain.models import (
    Discrepancia,
    EventoPagoRecibido,
    LineaLedger,
    TransaccionLedger,
)
from apps.users.api.serializers import UsuarioSerializer


class DiscrepanciaSerializer(serializers.ModelSerializer):
    resuelto_por = UsuarioSerializer(read_only=True)

    class Meta:
        model = Discrepancia
        fields = [
            'id', 'movimiento', 'consulta', 'evento', 'tipo', 'severidad',
            'estado_resolucion', 'resuelto_por', 'resuelto_at', 'notas', 'created_at',
        ]
        read_only_fields = fields


class DiscrepanciaResolverSerializer(serializers.Serializer):
    estado_resolucion = serializers.ChoiceField(
        choices=[
            Discrepancia.EstadoResolucion.RESUELTA,
            Discrepancia.EstadoResolucion.DESCARTADA,
            Discrepancia.EstadoResolucion.EN_REVISION,
        ],
    )
    notas = serializers.CharField(required=False, allow_blank=True, default='')


class EventoPagoRecibidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoPagoRecibido
        fields = ['id', 'event_id', 'event_type', 'schema_version', 'procesado_at', 'created_at']
        read_only_fields = fields


class LineaLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineaLedger
        fields = ['id', 'cuenta', 'tipo', 'monto']
        read_only_fields = fields


class TransaccionLedgerSerializer(serializers.ModelSerializer):
    lineas = LineaLedgerSerializer(many=True, read_only=True)

    class Meta:
        model = TransaccionLedger
        fields = ['id', 'referencia_evento', 'created_at', 'lineas']
        read_only_fields = fields
