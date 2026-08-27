from django.contrib import admin

from apps.conciliacion.domain.models import (
    Banco,
    ConsultaConciliacionProveedor,
    CuentaContable,
    Discrepancia,
    EventoPagoRecibido,
    LineaLedger,
    MovimientoBancario,
    ReporteERP,
    TransaccionLedger,
)


@admin.register(CuentaContable)
class CuentaContableAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'activa']
    search_fields = ['codigo', 'nombre']


@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'activo']
    search_fields = ['codigo', 'nombre']


@admin.register(EventoPagoRecibido)
class EventoPagoRecibidoAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_type', 'procesado_at', 'created_at']
    list_filter = ['event_type']
    search_fields = ['event_id']


@admin.register(ConsultaConciliacionProveedor)
class ConsultaConciliacionProveedorAdmin(admin.ModelAdmin):
    list_display = ['referencia_corta', 'banco', 'resultado_interpretado', 'fecha_pago']
    list_filter = ['resultado_interpretado', 'banco']
    search_fields = ['referencia_corta', 'telefono_pagador']


@admin.register(MovimientoBancario)
class MovimientoBancarioAdmin(admin.ModelAdmin):
    list_display = ['referencia_banco', 'banco', 'monto', 'estado_conciliacion', 'fecha']
    list_filter = ['estado_conciliacion', 'banco']
    search_fields = ['referencia_banco']


@admin.register(TransaccionLedger)
class TransaccionLedgerAdmin(admin.ModelAdmin):
    list_display = ['id', 'referencia_evento', 'created_at']


@admin.register(LineaLedger)
class LineaLedgerAdmin(admin.ModelAdmin):
    list_display = ['transaccion', 'cuenta', 'tipo', 'monto']
    list_filter = ['tipo', 'cuenta']


@admin.register(Discrepancia)
class DiscrepanciaAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'severidad', 'estado_resolucion', 'resuelto_por', 'created_at']
    list_filter = ['tipo', 'severidad', 'estado_resolucion']


@admin.register(ReporteERP)
class ReporteERPAdmin(admin.ModelAdmin):
    list_display = ['referencia_externa', 'fecha']
    search_fields = ['referencia_externa']
