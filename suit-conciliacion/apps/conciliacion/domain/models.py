from django.db import models

from apps.shared.domain.fields import EncryptedCharField, EncryptedJSONField
from apps.shared.domain.models import BaseModel
from apps.users.domain.models import Usuario


# ---------------------------------------------------------------------------
# 3.1 Catálogos
# ---------------------------------------------------------------------------

class CuentaContable(BaseModel):
    """Plan de cuentas del ledger de doble entrada."""

    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    nombre = models.CharField(max_length=150)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Cuenta contable'
        verbose_name_plural = 'Cuentas contables'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Banco(BaseModel):
    """Catálogo local de bancos (código SUDEBAN/BCV, 4 dígitos). Sin FK cruzada con Orquestador."""

    codigo = models.CharField(max_length=4, unique=True, db_index=True)
    nombre = models.CharField(max_length=150)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


# ---------------------------------------------------------------------------
# 3.2 Ingesta de eventos
# ---------------------------------------------------------------------------

class EventoPagoRecibido(BaseModel):
    """Espejo local de un evento `pago.*` consumido desde el outbox del Orquestador."""

    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=100)
    # Cifrado (Bloque #16): el payload de `pago.confirmado` trae en claro
    # cedula_pagador/telefono_pagador (ver contrato-evento-pago-confirmado.md).
    payload = EncryptedJSONField()
    schema_version = models.PositiveSmallIntegerField()
    procesado_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Evento de pago recibido'
        verbose_name_plural = 'Eventos de pago recibidos'

    def __str__(self):
        return f'{self.event_type} ({self.event_id})'


# ---------------------------------------------------------------------------
# 3.2b Conciliación real con BDV — consulta síncrona por transacción
# ---------------------------------------------------------------------------

class ConsultaConciliacionProveedor(BaseModel):
    class ResultadoInterpretado(models.TextChoices):
        CONCILIADO = 'conciliado', 'Conciliado'
        NO_ENCONTRADO = 'no_encontrado', 'No encontrado'
        MONTO_NO_COINCIDE = 'monto_no_coincide', 'Monto no coincide'
        YA_CONCILIADO = 'ya_conciliado', 'Ya conciliado'
        ERROR_CREDENCIALES = 'error_credenciales', 'Error de credenciales'
        PENDIENTE_REVISION = 'pendiente_revision', 'Pendiente de revisión'

    evento = models.ForeignKey(
        EventoPagoRecibido, on_delete=models.CASCADE, related_name='consultas_conciliacion',
    )
    banco = models.ForeignKey(
        Banco, on_delete=models.PROTECT, related_name='consultas_conciliacion',
    )
    referencia_corta = models.CharField(max_length=20, db_index=True)
    # Cifrados (Bloque #16, auditoría de seguridad): nunca se filtran por
    # igualdad exacta en ningún service (referencia_corta ya cubre el
    # matching) — EncryptedField no permite db_index/unique de todos modos.
    # Sin max_length: storage es TextField (el ciphertext es más largo que
    # el texto original), ver apps/shared/domain/fields.py.
    telefono_pagador = EncryptedCharField()
    cedula_pagador = EncryptedCharField(blank=True)
    cedula_confiable = models.BooleanField(default=False)
    importe_esperado = models.DecimalField(max_digits=19, decimal_places=2)
    # DateField (no DateTimeField): el contrato de `pago.confirmado` y el
    # request/response de getMovement/v2 mandan `fecha_pago` como AAAA-MM-DD,
    # sin hora (investigaciones/contrato-evento-pago-confirmado.md).
    fecha_pago = models.DateField()
    codigo_respuesta_raw = models.CharField(max_length=20)
    mensaje_respuesta_raw = models.TextField(blank=True)
    resultado_interpretado = models.CharField(max_length=30, choices=ResultadoInterpretado.choices)
    payload_crudo = EncryptedJSONField()  # cifrado (Bloque #16): respuesta cruda íntegra del proveedor

    class Meta:
        verbose_name = 'Consulta de conciliación al proveedor'
        verbose_name_plural = 'Consultas de conciliación al proveedor'

    def __str__(self):
        return f'{self.referencia_corta} -> {self.resultado_interpretado}'


class MovimientoBancario(BaseModel):
    """Modelo genérico para proveedores que entreguen extracto batch (no BDV, ver 3.2b)."""

    class EstadoConciliacion(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        CONCILIADO = 'conciliado', 'Conciliado'
        DISCREPANTE = 'discrepante', 'Discrepante'

    banco = models.ForeignKey(Banco, on_delete=models.PROTECT, related_name='movimientos')
    fecha = models.DateTimeField()
    referencia_banco = models.CharField(max_length=50)
    monto = models.DecimalField(max_digits=19, decimal_places=2)
    estado_conciliacion = models.CharField(
        max_length=20, choices=EstadoConciliacion.choices,
        default=EstadoConciliacion.PENDIENTE, db_index=True,
    )

    class Meta:
        verbose_name = 'Movimiento bancario'
        verbose_name_plural = 'Movimientos bancarios'

    def __str__(self):
        return f'{self.referencia_banco} ({self.monto})'


# ---------------------------------------------------------------------------
# 3.3 Ledger de doble entrada
# ---------------------------------------------------------------------------

class TransaccionLedger(BaseModel):
    """Agrupador de líneas balanceadas. `PROTECT`: nunca desaparece en cascada."""

    referencia_evento = models.ForeignKey(
        EventoPagoRecibido, on_delete=models.PROTECT, related_name='transacciones_ledger',
    )
    # Sin FK real: Conciliación y Orquestador corren en bases Postgres separadas
    # (database-per-service), una FK cruzada entre bases no es técnicamente
    # posible. Mismo patrón que AplicacionRegistrada.app_origen_id del lado del
    # Orquestador. Se extrae de evento.payload['aplicacion_id'] al registrar la
    # transacción (ver LedgerService.registrar_transaccion).
    aplicacion_id = models.UUIDField(db_index=True)

    class Meta:
        verbose_name = 'Transacción de ledger'
        verbose_name_plural = 'Transacciones de ledger'
        db_table = 'conciliacion_transaccion_ledger'

    def __str__(self):
        return f'TransaccionLedger {self.id}'


class LineaLedger(BaseModel):
    class Tipo(models.TextChoices):
        DEBITO = 'debito', 'Débito'
        CREDITO = 'credito', 'Crédito'

    transaccion = models.ForeignKey(TransaccionLedger, on_delete=models.CASCADE, related_name='lineas')
    cuenta = models.ForeignKey(CuentaContable, on_delete=models.PROTECT, related_name='lineas_ledger')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=19, decimal_places=2)

    class Meta:
        verbose_name = 'Línea de ledger'
        verbose_name_plural = 'Líneas de ledger'
        db_table = 'conciliacion_linea_ledger'
        constraints = [
            models.CheckConstraint(condition=models.Q(monto__gt=0), name='linea_ledger_monto_positivo'),
        ]

    def __str__(self):
        return f'{self.tipo} {self.monto} ({self.cuenta.codigo})'


# ---------------------------------------------------------------------------
# 3.4 Matching e importación bancaria
# ---------------------------------------------------------------------------

class Discrepancia(BaseModel):
    class Tipo(models.TextChoices):
        SIN_MOVIMIENTO_BANCARIO = 'sin_movimiento_bancario', 'Sin movimiento bancario'
        MONTO_NO_COINCIDE = 'monto_no_coincide', 'Monto no coincide'
        DUPLICADO = 'duplicado', 'Duplicado'
        ERROR_PROVEEDOR = 'error_proveedor', 'Error del proveedor'
        PENDIENTE_REVISION_MANUAL = 'pendiente_revision_manual', 'Pendiente de revisión manual'

    class Severidad(models.TextChoices):
        BAJA = 'baja', 'Baja'
        MEDIA = 'media', 'Media'
        ALTA = 'alta', 'Alta'
        CRITICA = 'critica', 'Crítica'

    class EstadoResolucion(models.TextChoices):
        ABIERTA = 'abierta', 'Abierta'
        EN_REVISION = 'en_revision', 'En revisión'
        RESUELTA = 'resuelta', 'Resuelta'
        DESCARTADA = 'descartada', 'Descartada'

    movimiento = models.ForeignKey(
        MovimientoBancario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='discrepancias',
    )
    consulta = models.ForeignKey(
        ConsultaConciliacionProveedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='discrepancias',
    )
    evento = models.ForeignKey(
        EventoPagoRecibido, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='discrepancias',
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    severidad = models.CharField(max_length=10, choices=Severidad.choices)
    estado_resolucion = models.CharField(
        max_length=15, choices=EstadoResolucion.choices,
        default=EstadoResolucion.ABIERTA, db_index=True,
    )
    resuelto_por = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='discrepancias_resueltas',
    )
    resuelto_at = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Discrepancia'
        verbose_name_plural = 'Discrepancias'
        indexes = [
            models.Index(fields=['estado_resolucion', 'severidad']),
        ]

    def __str__(self):
        return f'{self.tipo} [{self.severidad}] - {self.estado_resolucion}'


class ReporteERP(BaseModel):
    """Trazabilidad de lo exportado al ERP contable."""

    fecha = models.DateTimeField()
    referencia_externa = models.CharField(max_length=100)
    payload = models.JSONField()

    class Meta:
        verbose_name = 'Reporte ERP'
        verbose_name_plural = 'Reportes ERP'

    def __str__(self):
        return f'ReporteERP {self.referencia_externa}'
