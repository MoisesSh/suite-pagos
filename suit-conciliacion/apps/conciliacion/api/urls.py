from django.urls import path

from apps.conciliacion.api.views import (
    DiscrepanciaListView,
    DiscrepanciaResolverView,
    EventoPagoRecibidoListView,
    TransaccionLedgerDetailView,
    TransaccionLedgerListView,
)

app_name = 'conciliacion'

urlpatterns = [
    path('discrepancias/', DiscrepanciaListView.as_view(), name='discrepancias_list'),
    path('discrepancias/<uuid:pk>/resolver/', DiscrepanciaResolverView.as_view(), name='discrepancia_resolver'),
    path('eventos/', EventoPagoRecibidoListView.as_view(), name='eventos_list'),
    path('transacciones-ledger/', TransaccionLedgerListView.as_view(), name='transacciones_ledger_list'),
    path('transacciones-ledger/<uuid:pk>/', TransaccionLedgerDetailView.as_view(), name='transaccion_ledger_detail'),
]
