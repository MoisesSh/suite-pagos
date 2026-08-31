from django.db import transaction


class LedgerService:
    """Crea asientos de doble entrada. El balance débito=crédito se fuerza a nivel de
    motor Postgres (constraint trigger `DEFERRABLE INITIALLY DEFERRED` sobre
    `LineaLedger`, ver migración 0002) — si las líneas no balancean, el `COMMIT` de
    esta transacción falla, no una validación en Python."""

    @staticmethod
    @transaction.atomic
    def registrar_transaccion(evento, lineas):
        """`lineas` es una lista de dicts: {'cuenta': CuentaContable, 'tipo': 'debito'|'credito', 'monto': Decimal}.
        `aplicacion_id` se extrae de `evento.payload['aplicacion_id']` (viaja en el
        contrato `pago.confirmado`, ver investigaciones/contrato-evento-pago-confirmado.md)."""
        from apps.conciliacion.domain.models import LineaLedger, TransaccionLedger

        transaccion = TransaccionLedger.objects.create(
            referencia_evento=evento, aplicacion_id=evento.payload['aplicacion_id'],
        )
        LineaLedger.objects.bulk_create([
            LineaLedger(transaccion=transaccion, **linea) for linea in lineas
        ])
        return transaccion
