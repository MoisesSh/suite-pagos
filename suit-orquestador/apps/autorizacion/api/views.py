from rest_framework import status, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.autorizacion.api.serializers import ValidarAccesoRequestSerializer
from apps.autorizacion.application.services import AccesoNoAutorizadoError, ValidacionAccesoService


class ValidarAccesoView(views.APIView):
    """Control de seguridad bloqueante (db-plan-pagos.md 2.0): valida
    dominio -> aplicación -> proveedor autorizado. No crea ninguna
    IntencionPago — eso queda para un endpoint posterior que consuma
    este resultado."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ValidarAccesoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            aplicacion = ValidacionAccesoService.validar(
                dominio=serializer.validated_data['dominio'],
                proveedor_codigo=serializer.validated_data['proveedor'],
            )
        except AccesoNoAutorizadoError as exc:
            return Response({'autorizado': False, 'motivo': exc.motivo}, status=status.HTTP_403_FORBIDDEN)

        return Response({'autorizado': True, 'aplicacion': aplicacion.nombre}, status=status.HTTP_200_OK)
