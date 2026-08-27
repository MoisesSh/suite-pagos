from django.urls import path

from apps.autorizacion.api.views import ValidarAccesoView

app_name = 'autorizacion'
urlpatterns = [
    path('validar-acceso/', ValidarAccesoView.as_view(), name='validar_acceso'),
]
