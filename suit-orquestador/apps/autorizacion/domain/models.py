from datetime import timedelta

from django.db import models
from django.utils import timezone
from uuid_extensions import uuid7 as _uuid7


def generar_uuid7():
    """Wrapper propio: `uuid_extensions.uuid7` no serializa limpio en migraciones
    (su __module__ colisiona con el submódulo del mismo nombre)."""
    return _uuid7()


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=generar_uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AppendOnlyModel(models.Model):
    """Sin updated_at: filas de auditoría que nunca se editan tras insertarse."""
    id = models.UUIDField(primary_key=True, default=generar_uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


# --- 2.1 Catálogos ---------------------------------------------------------

class Moneda(BaseModel):
    """Catálogo (no TextChoices): `activo` debe poder alternarse sin deploy,
    ver db-plan-pagos.md sección 5, punto 3."""
    codigo = models.CharField(max_length=3, unique=True, db_index=True)
    nombre = models.CharField(max_length=50)
    activo = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'

    def __str__(self):
        return self.codigo


class MedioPago(BaseModel):
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Medio de pago'
        verbose_name_plural = 'Medios de pago'

    def __str__(self):
        return self.nombre


class ProveedorPago(BaseModel):
    medio_pago = models.ForeignKey(MedioPago, on_delete=models.PROTECT, related_name='proveedores')
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Proveedor de pago'
        verbose_name_plural = 'Proveedores de pago'

    def __str__(self):
        return self.nombre


class Banco(BaseModel):
    codigo = models.CharField(max_length=4, unique=True, db_index=True, help_text='Código SUDEBAN/BCV de 4 dígitos.')
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class TipoOperacionProveedor(BaseModel):
    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='tipos_operacion')
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Tipo de operación de proveedor'
        verbose_name_plural = 'Tipos de operación de proveedor'
        constraints = [
            models.UniqueConstraint(fields=['proveedor', 'codigo'], name='uniq_tipo_operacion_proveedor_codigo'),
        ]

    def __str__(self):
        return f'{self.proveedor.codigo}:{self.codigo}'


class CodigoRespuestaProveedor(BaseModel):
    class Categoria(models.TextChoices):
        EXITO = 'exito', 'Éxito'
        DUPLICADO_IDEMPOTENTE = 'duplicado_idempotente', 'Duplicado idempotente'
        ERROR_NEGOCIO = 'error_negocio', 'Error de negocio'
        ERROR_TECNICO = 'error_tecnico', 'Error técnico'

    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='codigos_respuesta')
    codigo = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=255)
    categoria = models.CharField(max_length=25, choices=Categoria.choices, db_index=True)

    class Meta:
        verbose_name = 'Código de respuesta de proveedor'
        verbose_name_plural = 'Códigos de respuesta de proveedor'
        constraints = [
            models.UniqueConstraint(fields=['proveedor', 'codigo'], name='uniq_codigo_respuesta_proveedor_codigo'),
        ]

    def __str__(self):
        return f'{self.proveedor.codigo}:{self.codigo}'


# --- 2.0 Registro de aplicaciones y dominios autorizados -------------------

class AplicacionRegistrada(BaseModel):
    nombre = models.CharField(max_length=150)
    app_origen_id = models.UUIDField(
        unique=True,
        help_text='Id lógico de AppConsumidora en el Developer Portal (sin FK real, sistema externo).',
    )
    activa = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'Aplicación registrada'
        verbose_name_plural = 'Aplicaciones registradas'

    def __str__(self):
        return self.nombre


class DominioPermitido(BaseModel):
    aplicacion = models.ForeignKey(AplicacionRegistrada, on_delete=models.CASCADE, related_name='dominios')
    dominio = models.CharField(max_length=255, unique=True, db_index=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Dominio permitido'
        verbose_name_plural = 'Dominios permitidos'

    def __str__(self):
        return self.dominio


class AplicacionProveedorPermitido(BaseModel):
    aplicacion = models.ForeignKey(
        AplicacionRegistrada, on_delete=models.CASCADE, related_name='proveedores_autorizados',
    )
    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='aplicaciones_autorizadas')
    activo = models.BooleanField(default=True)
    autorizado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Autorización aplicación-proveedor'
        verbose_name_plural = 'Autorizaciones aplicación-proveedor'
        constraints = [
            models.UniqueConstraint(fields=['aplicacion', 'proveedor'], name='uniq_aplicacion_proveedor'),
        ]

    def __str__(self):
        return f'{self.aplicacion.nombre} -> {self.proveedor.nombre}'


# --- 2.3 Idempotencia --------------------------------------------------

def default_expiracion_idempotency_key():
    return timezone.now() + timedelta(hours=48)


class IdempotencyKey(BaseModel):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        COMPLETADO = 'completado', 'Completado'
        RECHAZADO = 'rechazado', 'Rechazado'

    key = models.UUIDField(unique=True, db_index=True)
    request_hash = models.CharField(max_length=64)
    response_snapshot = models.JSONField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    expires_at = models.DateTimeField(default=default_expiracion_idempotency_key)

    class Meta:
        verbose_name = 'Clave de idempotencia'
        verbose_name_plural = 'Claves de idempotencia'

    def __str__(self):
        return str(self.key)


# --- 2.2 Agregado de pago ---------------------------------------------------

class IntencionPago(BaseModel):
    class EstadoPago(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        AUTORIZADO = 'autorizado', 'Autorizado'
        CAPTURADO = 'capturado', 'Capturado'
        ANULADO = 'anulado', 'Anulado'
        FALLIDO = 'fallido', 'Fallido'
        REEMBOLSADO = 'reembolsado', 'Reembolsado'
        EXPIRADO = 'expirado', 'Expirado'

    class RoutingFlag(models.TextChoices):
        LEGACY = 'legacy', 'Legacy'
        CANARIO = 'canario', 'Canario'

    monto = models.DecimalField(max_digits=19, decimal_places=2)
    moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, related_name='intenciones_pago')
    medio_pago = models.ForeignKey(MedioPago, on_delete=models.PROTECT, related_name='intenciones_pago')
    aplicacion = models.ForeignKey(AplicacionRegistrada, on_delete=models.PROTECT, related_name='intenciones_pago')
    idempotency_key = models.OneToOneField(
        IdempotencyKey, on_delete=models.PROTECT, related_name='intencion_pago', null=True, blank=True,
    )
    estado_actual = models.CharField(
        max_length=15, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE, db_index=True,
    )
    routing_flag = models.CharField(max_length=10, choices=RoutingFlag.choices, default=RoutingFlag.LEGACY)

    class Meta:
        verbose_name = 'Intención de pago'
        verbose_name_plural = 'Intenciones de pago'

    def __str__(self):
        return f'{self.id} ({self.estado_actual})'


class TransicionEstadoPago(AppendOnlyModel):
    pago = models.ForeignKey(IntencionPago, on_delete=models.CASCADE, related_name='transiciones')
    estado_anterior = models.CharField(
        max_length=15, choices=IntencionPago.EstadoPago.choices, null=True, blank=True,
    )
    estado_nuevo = models.CharField(max_length=15, choices=IntencionPago.EstadoPago.choices)

    class Meta:
        verbose_name = 'Transición de estado de pago'
        verbose_name_plural = 'Transiciones de estado de pago'
        indexes = [
            models.Index(fields=['pago', '-created_at'], name='idx_transicion_pago_created'),
        ]

    def __str__(self):
        return f'{self.pago_id}: {self.estado_anterior} -> {self.estado_nuevo}'


class OperacionPagoBase(BaseModel):
    """Campos genéricos de proveedor compartidos por Autorizacion/Captura/Anulacion/Reembolso.
    Nunca un campo específico de un banco — principio de multi-proveedor sin choque
    (db-plan-pagos.md sección 1)."""
    referencia_proveedor = models.CharField(max_length=100)
    referencia_corta = models.CharField(max_length=20, blank=True)
    identificador_interbancario = models.CharField(max_length=62, blank=True)
    payload_crudo = models.JSONField()
    monto = models.DecimalField(max_digits=19, decimal_places=2)

    class Meta:
        abstract = True


class Autorizacion(OperacionPagoBase):
    pago = models.ForeignKey(IntencionPago, on_delete=models.CASCADE, related_name='autorizaciones')
    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='autorizaciones')
    tipo_operacion = models.ForeignKey(
        TipoOperacionProveedor, on_delete=models.PROTECT, related_name='autorizaciones',
    )
    codigo_respuesta = models.ForeignKey(
        CodigoRespuestaProveedor, on_delete=models.PROTECT, related_name='autorizaciones',
    )
    otp_solicitado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Autorización'
        verbose_name_plural = 'Autorizaciones'

    def __str__(self):
        return f'{self.pago_id}:{self.referencia_proveedor}'


class Captura(OperacionPagoBase):
    pago = models.ForeignKey(IntencionPago, on_delete=models.CASCADE, related_name='capturas')
    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='capturas')
    tipo_operacion = models.ForeignKey(TipoOperacionProveedor, on_delete=models.PROTECT, related_name='capturas')
    codigo_respuesta = models.ForeignKey(
        CodigoRespuestaProveedor, on_delete=models.PROTECT, related_name='capturas',
    )

    class Meta:
        verbose_name = 'Captura'
        verbose_name_plural = 'Capturas'

    def __str__(self):
        return f'{self.pago_id}:{self.referencia_proveedor}'


class Anulacion(OperacionPagoBase):
    pago = models.ForeignKey(IntencionPago, on_delete=models.CASCADE, related_name='anulaciones')
    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='anulaciones')
    tipo_operacion = models.ForeignKey(TipoOperacionProveedor, on_delete=models.PROTECT, related_name='anulaciones')
    codigo_respuesta = models.ForeignKey(
        CodigoRespuestaProveedor, on_delete=models.PROTECT, related_name='anulaciones',
    )

    class Meta:
        verbose_name = 'Anulación'
        verbose_name_plural = 'Anulaciones'

    def __str__(self):
        return f'{self.pago_id}:{self.referencia_proveedor}'


class Reembolso(OperacionPagoBase):
    pago = models.ForeignKey(IntencionPago, on_delete=models.CASCADE, related_name='reembolsos')
    proveedor = models.ForeignKey(ProveedorPago, on_delete=models.PROTECT, related_name='reembolsos')
    tipo_operacion = models.ForeignKey(TipoOperacionProveedor, on_delete=models.PROTECT, related_name='reembolsos')
    codigo_respuesta = models.ForeignKey(
        CodigoRespuestaProveedor, on_delete=models.PROTECT, related_name='reembolsos',
    )

    class Meta:
        verbose_name = 'Reembolso'
        verbose_name_plural = 'Reembolsos'

    def __str__(self):
        return f'{self.pago_id}:{self.referencia_proveedor}'


# --- 2.3 Outbox pattern ------------------------------------------------

class EventoOutbox(AppendOnlyModel):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ENVIADO = 'enviado', 'Enviado'
        FALLIDO = 'fallido', 'Fallido'

    pago = models.ForeignKey(IntencionPago, on_delete=models.CASCADE, related_name='eventos_outbox')
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    schema_version = models.PositiveSmallIntegerField()
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Evento de outbox'
        verbose_name_plural = 'Eventos de outbox'

    def __str__(self):
        return f'{self.event_type} ({self.estado})'
