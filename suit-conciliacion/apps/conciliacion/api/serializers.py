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
    transaccion_ledger_id = serializers.SerializerMethodField()

    class Meta:
        model = Discrepancia
        fields = [
            'id', 'movimiento', 'consulta', 'evento', 'tipo', 'severidad',
            'estado_resolucion', 'resuelto_por', 'resuelto_at', 'notas', 'created_at',
            'transaccion_ledger_id',
        ]
        read_only_fields = fields

    def get_transaccion_ledger_id(self, obj):
        if obj.evento is None:
            return None
        transaccion = obj.evento.transacciones_ledger.first()
        return transaccion.id if transaccion else None


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
    transaccion_ledger_id = serializers.SerializerMethodField()

    class Meta:
        model = EventoPagoRecibido
        fields = [
            'id', 'event_id', 'event_type', 'schema_version', 'procesado_at', 'created_at',
            'transaccion_ledger_id',
        ]
        read_only_fields = fields

    def get_transaccion_ledger_id(self, obj):
        transaccion = obj.transacciones_ledger.first()
        return transaccion.id if transaccion else None


class LineaLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineaLedger
        fields = ['id', 'cuenta', 'tipo', 'monto']
        read_only_fields = fields


class TransaccionLedgerSerializer(serializers.ModelSerializer):
    lineas = LineaLedgerSerializer(many=True, read_only=True)

    class Meta:
        model = TransaccionLedger
        fields = ['id', 'referencia_evento', 'aplicacion_id', 'created_at', 'lineas']
        read_only_fields = fields
