from django.contrib import admin

from apps.autorizacion.domain.models import (
    AplicacionProveedorPermitido,
    AplicacionRegistrada,
    Anulacion,
    Autorizacion,
    Banco,
    Captura,
    CodigoRespuestaProveedor,
    DominioPermitido,
    EventoOutbox,
    IdempotencyKey,
    IntencionPago,
    MedioPago,
    Moneda,
    ProveedorPago,
    Reembolso,
    TipoOperacionProveedor,
    TransicionEstadoPago,
)


# --- Catálogos ---------------------------------------------------------

@admin.register(Moneda)
class MonedaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activo',)


@admin.register(MedioPago)
class MedioPagoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activo',)


@admin.register(ProveedorPago)
class ProveedorPagoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'medio_pago', 'activo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('medio_pago', 'activo')


@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activo',)


@admin.register(TipoOperacionProveedor)
class TipoOperacionProveedorAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'codigo', 'nombre')
    search_fields = ('codigo', 'nombre')
    list_filter = ('proveedor',)


@admin.register(CodigoRespuestaProveedor)
class CodigoRespuestaProveedorAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'codigo', 'categoria', 'descripcion')
    search_fields = ('codigo', 'descripcion')
    list_filter = ('proveedor', 'categoria')


# --- Registro de seguridad (2.0) ---------------------------------------

class DominioPermitidoInline(admin.TabularInline):
    model = DominioPermitido
    extra = 0


class AplicacionProveedorPermitidoInline(admin.TabularInline):
    model = AplicacionProveedorPermitido
    extra = 0
    readonly_fields = ('autorizado_en',)


@admin.register(AplicacionRegistrada)
class AplicacionRegistradaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'app_origen_id', 'activa')
    search_fields = ('nombre', 'app_origen_id')
    list_filter = ('activa',)
    inlines = (DominioPermitidoInline, AplicacionProveedorPermitidoInline)


@admin.register(DominioPermitido)
class DominioPermitidoAdmin(admin.ModelAdmin):
    list_display = ('dominio', 'aplicacion', 'activo')
    search_fields = ('dominio',)
    list_filter = ('activo',)


@admin.register(AplicacionProveedorPermitido)
class AplicacionProveedorPermitidoAdmin(admin.ModelAdmin):
    list_display = ('aplicacion', 'proveedor', 'activo', 'autorizado_en')
    list_filter = ('activo', 'proveedor')
    readonly_fields = ('autorizado_en',)


# --- Idempotencia --------------------------------------------------

@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'estado', 'expires_at', 'created_at')
    search_fields = ('key',)
    list_filter = ('estado',)
    readonly_fields = ('created_at', 'updated_at')


# --- Agregado de pago (2.2) ---------------------------------------------

@admin.register(IntencionPago)
class IntencionPagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'monto', 'moneda', 'medio_pago', 'aplicacion', 'estado_actual', 'routing_flag')
    list_filter = ('estado_actual', 'routing_flag', 'moneda', 'medio_pago')
    search_fields = ('id',)
    # estado_actual es un espejo mantenido automáticamente por el servicio de transición
    # (ver db-plan-pagos.md 2.2) — nunca editable a mano desde el admin.
    readonly_fields = ('estado_actual', 'created_at', 'updated_at')


@admin.register(TransicionEstadoPago)
class TransicionEstadoPagoAdmin(admin.ModelAdmin):
    list_display = ('pago', 'estado_anterior', 'estado_nuevo', 'created_at')
    list_filter = ('estado_anterior', 'estado_nuevo')
    readonly_fields = ('created_at',)

    # Tabla append-only: la validez de la transición la fuerza el trigger de Postgres,
    # pero además no se permite editar ni borrar una fila ya escrita desde el admin.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OperacionPagoAdminBase(admin.ModelAdmin):
    list_display = ('pago', 'proveedor', 'referencia_proveedor', 'referencia_corta', 'monto', 'codigo_respuesta')
    list_filter = ('proveedor', 'codigo_respuesta')
    search_fields = ('referencia_proveedor', 'referencia_corta', 'identificador_interbancario')


@admin.register(Autorizacion)
class AutorizacionAdmin(OperacionPagoAdminBase):
    list_display = OperacionPagoAdminBase.list_display + ('otp_solicitado_at',)


@admin.register(Captura)
class CapturaAdmin(OperacionPagoAdminBase):
    pass


@admin.register(Anulacion)
class AnulacionAdmin(OperacionPagoAdminBase):
    pass


@admin.register(Reembolso)
class ReembolsoAdmin(OperacionPagoAdminBase):
    pass


# --- Outbox (2.3) -----------------------------------------------------

@admin.register(EventoOutbox)
class EventoOutboxAdmin(admin.ModelAdmin):
    list_display = ('pago', 'event_type', 'estado', 'schema_version', 'created_at', 'sent_at')
    list_filter = ('estado', 'event_type')
    readonly_fields = ('created_at',)
