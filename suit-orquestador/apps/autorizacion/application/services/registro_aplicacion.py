import uuid

from django.db import IntegrityError, transaction

from apps.autorizacion.domain.models import (
    AplicacionProveedorPermitido,
    AplicacionRegistrada,
    DominioPermitido,
    ProveedorPago,
)


class ProveedorNoEncontradoError(Exception):
    """Código de ProveedorPago inexistente."""


class DominioYaRegistradoError(Exception):
    """DominioPermitido.dominio es único global — no se reasigna a otra app."""

    def __init__(self, dominio):
        self.dominio = dominio
        super().__init__(f'El dominio {dominio!r} ya está registrado para otra aplicación.')


class RegistroAplicacionService:
    """CRUD mínimo de db-plan-pagos.md sección 2.0 (registro de apps/dominios
    autorizados) — lo que suit-portal necesita para dejar de estar mockeado."""

    @staticmethod
    @transaction.atomic
    def registrar(*, nombre, dominio, proveedor_codigo, app_origen_id=None):
        try:
            proveedor = ProveedorPago.objects.get(codigo=proveedor_codigo)
        except ProveedorPago.DoesNotExist:
            raise ProveedorNoEncontradoError(proveedor_codigo)

        aplicacion = AplicacionRegistrada.objects.create(
            nombre=nombre,
            # app_origen_id: referencia lógica a AppConsumidora del Developer
            # Portal (db-plan-pagos.md 2.0). suit-portal todavía no tiene ese
            # modelo propio — mientras tanto, se genera acá; cuando lo tenga,
            # empieza a mandarlo real sin romper este contrato.
            app_origen_id=app_origen_id or uuid.uuid4(),
        )

        try:
            DominioPermitido.objects.create(aplicacion=aplicacion, dominio=dominio)
        except IntegrityError:
            raise DominioYaRegistradoError(dominio)

        AplicacionProveedorPermitido.objects.create(aplicacion=aplicacion, proveedor=proveedor)

        return aplicacion

    @staticmethod
    def activar_desactivar(aplicacion, activa):
        aplicacion.activa = activa
        aplicacion.save(update_fields=['activa', 'updated_at'])
        return aplicacion
