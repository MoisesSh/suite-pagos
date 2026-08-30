from rest_framework import generics, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.autorizacion.api.admin_serializers import (
    AdminAplicacionActivarSerializer,
    AdminAplicacionCrearSerializer,
    AdminAplicacionListItemSerializer,
    AdminAplicacionSerializer,
)
from apps.autorizacion.application.services.registro_aplicacion import (
    DominioYaRegistradoError,
    ProveedorNoEncontradoError,
    RegistroAplicacionService,
)
from apps.autorizacion.domain.models import AplicacionRegistrada


class AdminAplicacionListCreateView(generics.ListCreateAPIView):
    """CRUD mínimo de registro de apps/dominios (db-plan-pagos.md 2.0) para
    administradores de Conatel — no confundir con los endpoints públicos AllowAny
    del resto de esta app. Bajo volumen, uso interno: TokenAuthentication sobre
    django.contrib.auth.User (is_staff), no JWT propio."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return AplicacionRegistrada.objects.prefetch_related(
            'dominios', 'proveedores_autorizados__proveedor',
        ).order_by('-created_at')

    def get_serializer_class(self):
        return AdminAplicacionCrearSerializer if self.request.method == 'POST' else AdminAplicacionListItemSerializer

    def post(self, request, *args, **kwargs):
        entrada = AdminAplicacionCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        try:
            aplicacion = RegistroAplicacionService.registrar(
                nombre=datos['nombre'],
                dominio=datos['dominio'],
                proveedor_codigo=datos['proveedor'],
                app_origen_id=datos.get('app_origen_id'),
                webhook_url=datos.get('webhook_url'),
            )
        except ProveedorNoEncontradoError:
            return Response({'error': 'proveedor_no_encontrado'}, status=status.HTTP_400_BAD_REQUEST)
        except DominioYaRegistradoError:
            return Response({'error': 'dominio_ya_registrado'}, status=status.HTTP_409_CONFLICT)

        salida = AdminAplicacionSerializer({
            'id': aplicacion.id, 'nombre': aplicacion.nombre,
            'dominio': datos['dominio'], 'proveedor': datos['proveedor'],
        })
        return Response(salida.data, status=status.HTTP_201_CREATED)


class AdminAplicacionActivarView(generics.UpdateAPIView):
    """PATCH {"activa": true|false} y/o {"webhook_url": "..."} — kill switch de
    nivel superior (el mismo que consulta ValidacionAccesoService) y configuración
    del webhook server-to-server (Bloque #17 parte 2). No expone edición de
    dominio/proveedor individual todavía (fuera de alcance de ese bloque)."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]
    queryset = AplicacionRegistrada.objects.all()
    serializer_class = AdminAplicacionActivarSerializer
    http_method_names = ['patch']

    def perform_update(self, serializer):
        datos = serializer.validated_data
        if 'activa' in datos:
            RegistroAplicacionService.activar_desactivar(serializer.instance, datos['activa'])
        if 'webhook_url' in datos:
            RegistroAplicacionService.configurar_webhook(serializer.instance, datos['webhook_url'])
