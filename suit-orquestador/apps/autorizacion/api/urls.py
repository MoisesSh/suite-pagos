from django.urls import path

from apps.autorizacion.api.admin_views import AdminAplicacionActivarView, AdminAplicacionListCreateView
from apps.autorizacion.api.views import EjecutarCobroView, SolicitarOtpView, ValidarAccesoView

app_name = 'autorizacion'
urlpatterns = [
    path('validar-acceso/', ValidarAccesoView.as_view(), name='validar_acceso'),
    path('cobro/otp/', SolicitarOtpView.as_view(), name='cobro_otp'),
    path('cobro/', EjecutarCobroView.as_view(), name='cobro'),
    path('admin/aplicaciones/', AdminAplicacionListCreateView.as_view(), name='admin_aplicaciones'),
    path('admin/aplicaciones/<uuid:pk>/', AdminAplicacionActivarView.as_view(), name='admin_aplicacion_activar'),
]
