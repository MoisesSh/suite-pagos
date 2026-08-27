from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conciliacion.api.serializers import (
    DiscrepanciaResolverSerializer,
    DiscrepanciaSerializer,
    EventoPagoRecibidoSerializer,
    TransaccionLedgerSerializer,
)
from apps.conciliacion.application.services.matching import MatchingService
from apps.conciliacion.domain.models import Discrepancia, EventoPagoRecibido, TransaccionLedger
from apps.shared.api.serializers import MensajeRespuestaSerializer


class DiscrepanciaListView(generics.ListAPIView):
    serializer_class = DiscrepanciaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Discrepancia.objects.none()

        queryset = Discrepancia.objects.select_related('resuelto_por').order_by('-created_at')
        estado_resolucion = self.request.query_params.get('estado_resolucion')
        severidad = self.request.query_params.get('severidad')
        if estado_resolucion:
            queryset = queryset.filter(estado_resolucion=estado_resolucion)
        if severidad:
            queryset = queryset.filter(severidad=severidad)
        return queryset


class DiscrepanciaResolverView(views.APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DiscrepanciaResolverSerializer,
        responses={200: DiscrepanciaSerializer, 404: MensajeRespuestaSerializer},
    )
    def patch(self, request, pk):
        try:
            discrepancia = Discrepancia.objects.get(pk=pk)
        except Discrepancia.DoesNotExist:
            return Response({'error': 'Discrepancia no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = DiscrepanciaResolverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        discrepancia = MatchingService.resolver_discrepancia(
            discrepancia,
            usuario=request.user,
            estado_resolucion=serializer.validated_data['estado_resolucion'],
            notas=serializer.validated_data.get('notas', ''),
        )
        return Response(DiscrepanciaSerializer(discrepancia).data)


class EventoPagoRecibidoListView(generics.ListAPIView):
    serializer_class = EventoPagoRecibidoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['event_id', 'event_type']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return EventoPagoRecibido.objects.none()
        return EventoPagoRecibido.objects.order_by('-created_at')


class TransaccionLedgerDetailView(generics.RetrieveAPIView):
    serializer_class = TransaccionLedgerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TransaccionLedger.objects.none()
        return TransaccionLedger.objects.prefetch_related('lineas', 'lineas__cuenta')
