from django.db import transaction
from django.utils import timezone


class IngestaService:
    """Registra eventos `pago.*` consumidos desde RabbitMQ, deduplicando por `event_id`."""

    @staticmethod
    @transaction.atomic
    def registrar_evento(event_id, event_type, payload, schema_version):
        from apps.conciliacion.domain.models import EventoPagoRecibido

        evento, creado = EventoPagoRecibido.objects.get_or_create(
            event_id=event_id,
            defaults={
                'event_type': event_type,
                'payload': payload,
                'schema_version': schema_version,
            },
        )
        return evento, creado

    @staticmethod
    def marcar_procesado(evento):
        evento.procesado_at = timezone.now()
        evento.save(update_fields=['procesado_at', 'updated_at'])
