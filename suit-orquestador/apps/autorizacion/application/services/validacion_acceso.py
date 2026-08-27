from apps.autorizacion.domain.models import (
    AplicacionProveedorPermitido,
    AplicacionRegistrada,
    DominioPermitido,
    ProveedorPago,
)


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

        return ValidacionAccesoService._validar_aplicacion_proveedor(dominio_permitido.aplicacion, proveedor_codigo)

    @staticmethod
    def validar_por_aplicacion(aplicacion_id, proveedor_codigo):
        """Re-validación por identidad de aplicación (no por dominio) — usada en el POST
        de cobro dentro del flujo de checkout_token (research-seguridad-iframe.md sección 3:
        el Origin/Referer del submit dentro del iframe no refleja el dominio de la app
        consumidora, así que la identidad viaja en el token emitido por ValidarAccesoView,
        no se re-deriva del header). Repite las mismas comprobaciones de app/proveedor que
        `validar`, sin volver a resolver por dominio."""
        try:
            aplicacion = AplicacionRegistrada.objects.get(id=aplicacion_id)
        except AplicacionRegistrada.DoesNotExist:
            raise AccesoNoAutorizadoError('aplicacion_no_encontrada')

        return ValidacionAccesoService._validar_aplicacion_proveedor(aplicacion, proveedor_codigo)

    @staticmethod
    def _validar_aplicacion_proveedor(aplicacion, proveedor_codigo):
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
