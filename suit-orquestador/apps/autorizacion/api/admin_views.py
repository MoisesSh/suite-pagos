from rest_framework import generics, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.autorizacion.api.admin_serializers import (
    AdminAnularPagoRequestSerializer,
    AdminAplicacionActivarSerializer,
    AdminAplicacionCrearSerializer,
    AdminAplicacionListItemSerializer,
    AdminAplicacionSerializer,
)
from apps.autorizacion.application.services.flujo_cobro_c2p import FlujoCobroC2PService, PagoNoAnulableError
from apps.autorizacion.application.services.registro_aplicacion import (
    DominioYaRegistradoError,
    ProveedorNoEncontradoError,
    RegistroAplicacionService,
)
from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import AplicacionRegistrada, IntencionPago
from apps.autorizacion.infrastructure.adapters.bdv_c2p import BDVPagoMovilC2PAdapter


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


class AdminAnularPagoView(generics.GenericAPIView):
    """POST admin para forzar la anulación de un cobro C2P ya capturado (Bloque #22).
    Solo staff de Conatel puede pedirla — se dispara desde suit-panel, sin endpoint
    público equivalente para apps consumidoras. Sin ventana de tiempo propia: siempre
    se intenta contra BDV; si el banco la rechaza (por su propia ventana u otro motivo
    de negocio), ese rechazo se propaga tal cual, sin traducir a un mensaje propio."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]
    queryset = IntencionPago.objects.all()
    lookup_url_kwarg = 'id'

    def post(self, request, *args, **kwargs):
        pago = self.get_object()
        entrada = AdminAnularPagoRequestSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        adaptador = BDVPagoMovilC2PAdapter()
        try:
            anulacion = FlujoCobroC2PService.anular_cobro(
                pago, adaptador=adaptador,
                referencia_origen=entrada.validated_data.get('referencia_origen'),
            )
        except PagoNoAnulableError as exc:
            return Response(
                {'error': 'pago_no_anulable', 'estado_actual': exc.estado_actual}, status=status.HTTP_409_CONFLICT,
            )
        except ProveedorPagoError as exc:
            return Response(
                {'error': 'proveedor_rechazo_anulacion', 'codigo_proveedor': exc.codigo, 'mensaje': exc.mensaje},
                status=status.HTTP_409_CONFLICT,
            )
        except ProveedorPagoIndisponibleError:
            return Response({'error': 'proveedor_no_disponible'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'id': str(anulacion.id),
            'pago_id': str(pago.id),
            'estado_pago': pago.estado_actual,
            'codigo_respuesta': anulacion.codigo_respuesta.codigo,
        }, status=status.HTTP_200_OK)
