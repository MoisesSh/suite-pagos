class ProveedorPagoError(Exception):
    """Respuesta de negocio del proveedor con un código explícito (ej. BDV '1034' Saldo insuficiente).
    Distinta de una falla de transporte: el proveedor respondió, pero la operación no fue exitosa."""

    def __init__(self, codigo, mensaje, payload_crudo=None):
        self.codigo = codigo
        self.mensaje = mensaje
        self.payload_crudo = payload_crudo
        super().__init__(f'{codigo}: {mensaje}')


class ProveedorPagoIndisponibleError(Exception):
    """Falla de transporte (timeout, conexión rechazada, HTTP 5xx) — el proveedor no llegó
    a responder con un código de negocio. Distinguirla de ProveedorPagoError permite decidir
    si reintentar tiene sentido."""

    def __init__(self, detalle):
        self.detalle = detalle
        super().__init__(detalle)
