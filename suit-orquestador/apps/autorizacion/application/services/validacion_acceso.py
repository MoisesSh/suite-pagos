from apps.autorizacion.domain.models import AplicacionProveedorPermitido, DominioPermitido, ProveedorPago


class AccesoNoAutorizadoError(Exception):
    """Rechazo del control de seguridad de 2.0 — dominio/app/proveedor no autorizado."""

    def __init__(self, motivo):
        self.motivo = motivo
        super().__init__(motivo)


class ValidacionAccesoService:
    """Control de seguridad bloqueante de db-plan-pagos.md 2.0: resuelve
    dominio de origen -> DominioPermitido (activo) -> AplicacionRegistrada
    (activa) -> AplicacionProveedorPermitido (activo) para el ProveedorPago
    solicitado. Debe consultarse antes de crear cualquier IntencionPago."""

    @staticmethod
    def validar(dominio, proveedor_codigo):
        try:
            dominio_permitido = DominioPermitido.objects.select_related('aplicacion').get(dominio=dominio)
        except DominioPermitido.DoesNotExist:
            raise AccesoNoAutorizadoError('dominio_no_registrado')

        if not dominio_permitido.activo:
            raise AccesoNoAutorizadoError('dominio_inactivo')

        aplicacion = dominio_permitido.aplicacion
        if not aplicacion.activa:
            raise AccesoNoAutorizadoError('aplicacion_inactiva')

        try:
            proveedor = ProveedorPago.objects.get(codigo=proveedor_codigo)
        except ProveedorPago.DoesNotExist:
            raise AccesoNoAutorizadoError('proveedor_no_encontrado')

        autorizado = AplicacionProveedorPermitido.objects.filter(
            aplicacion=aplicacion, proveedor=proveedor, activo=True,
        ).exists()
        if not autorizado:
            raise AccesoNoAutorizadoError('proveedor_no_autorizado')

        return aplicacion
