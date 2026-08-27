"""Reglas de dominio puras del adaptador BDV (Banco de Venezuela) —
`POST /getMovement/v2`, contrato real documentado en
`investigaciones/research-brief-pagos.md` §4.2 (leído de
`Doc- API Conciliación Dummy.pdf`, v6). Sin I/O, sin ORM: solo interpreta
payloads ya recibidos. La llamada HTTP en sí es responsabilidad de una
futura capa de infraestructura (adaptador BDV), no implementada todavía.
"""

import re

from apps.conciliacion.domain.models import ConsultaConciliacionProveedor

# Código SUDEBAN/BCV de Banco de Venezuela — el propio banco que expone
# `getMovement/v2`. Toda consulta de Conciliación es sobre pagos recibidos
# en una cuenta BDV; lo que varía es el banco *origen* del pagador.
BANCO_BDV_CODIGO = '0102'

# BDV solo devuelve dos códigos de respuesta binarios (ver brief §4.2):
# 1000 = conciliado con éxito. 1010 = "no conciliado", un único código que
# agrupa 4 escenarios distintos (no encontrado, monto no coincide, ya
# conciliado, credenciales inválidas) — se distinguen solo por el texto de
# `message`, nunca por el código. El wording ya cambió entre versiones de
# la API del proveedor (v6 ajustó el mensaje de "ya conciliado"), por eso
# el crudo (`payload_crudo`) siempre se guarda aparte del resultado
# interpretado — permite reprocesar retroactivamente si el texto vuelve a
# cambiar.
CODIGO_EXITO = '1000'
CODIGO_NO_CONCILIADO = '1010'

_PATRON_NO_ENCONTRADO = re.compile(r'registro solicitado no existe', re.IGNORECASE)
_PATRON_YA_CONCILIADO = re.compile(r'ya fue conciliado anteriormente', re.IGNORECASE)
_PATRON_ERROR_CREDENCIALES = re.compile(r'no afiliado al producto', re.IGNORECASE)
# Formato real observado: "monto : 120.00 - estatus : Transacción realizada"
# (distinto del mensaje de éxito "Monto: 120.00 - estatus: ..." que viene con code=1000).
_PATRON_MONTO_NO_COINCIDE = re.compile(r'\bmonto\s*:', re.IGNORECASE)


def es_operacion_intrabanco_bdv(banco_origen_codigo):
    """True si el pagador también es BDV (BDV↔BDV). False = interbancario vía
    Suiche 7B, donde el banco sustituye `cedulaPagador` por "V" + RIF del
    comercio receptor — la cédula deja de ser confiable como identidad."""
    return banco_origen_codigo == BANCO_BDV_CODIGO


def requiere_cedula_estricta(banco_origen_codigo):
    """`reqCed` del request a `getMovement/v2` — solo `true` en BDV↔BDV."""
    return es_operacion_intrabanco_bdv(banco_origen_codigo)


def interpretar_respuesta_conciliacion(codigo_respuesta, mensaje_respuesta):
    """Traduce (code, message) de `getMovement/v2` al `ResultadoInterpretado`
    normalizado. Nunca falla en silencio: cualquier caso no reconocido cae en
    `pendiente_revision`, que siempre genera una `Discrepancia` (ver
    application/services/matching.py)."""
    codigo = str(codigo_respuesta)
    mensaje = mensaje_respuesta or ''

    if codigo == CODIGO_EXITO:
        return ConsultaConciliacionProveedor.ResultadoInterpretado.CONCILIADO

    if _PATRON_NO_ENCONTRADO.search(mensaje):
        return ConsultaConciliacionProveedor.ResultadoInterpretado.NO_ENCONTRADO
    if _PATRON_YA_CONCILIADO.search(mensaje):
        return ConsultaConciliacionProveedor.ResultadoInterpretado.YA_CONCILIADO
    if _PATRON_ERROR_CREDENCIALES.search(mensaje):
        return ConsultaConciliacionProveedor.ResultadoInterpretado.ERROR_CREDENCIALES
    if _PATRON_MONTO_NO_COINCIDE.search(mensaje):
        return ConsultaConciliacionProveedor.ResultadoInterpretado.MONTO_NO_COINCIDE

    return ConsultaConciliacionProveedor.ResultadoInterpretado.PENDIENTE_REVISION
