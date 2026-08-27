from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ResultadoOtp:
    codigo: str
    mensaje: str
    payload_crudo: dict


@dataclass(frozen=True)
class ResultadoCobro:
    codigo: str
    mensaje: str
    referencia_corta: Optional[str]
    identificador_interbancario: Optional[str]
    payload_crudo: dict


@dataclass(frozen=True)
class ResultadoAnulacion:
    codigo: str
    mensaje: str
    payload_crudo: dict


class PaymentProviderPort(ABC):
    """Puerto de salida para proveedores de pago (db-plan-pagos.md sección 1: multi-proveedor
    sin choque). Un adaptador nuevo (infrastructure/adapters/) implementa esta interfaz sin
    tocar el agregado de dominio ni la orquestación de application/."""

    @abstractmethod
    def generar_otp(self, *, cedula):
        """Dispara el envío de la clave OTP al pagador. No produce ninguna referencia
        transaccional — solo confirma que el proceso se inició."""
        raise NotImplementedError

    @abstractmethod
    def procesar_cobro(
        self, *, cedula, telefono_pagador, monto, banco_codigo, concepto, otp,
        moneda_codigo, tipo_operacion_codigo, telefono_comercio,
    ):
        """Ejecuta el cargo. Devuelve ResultadoCobro con las referencias del proveedor."""
        raise NotImplementedError

    @abstractmethod
    def anular(self, *, identificador_interbancario, referencia_origen=None):
        """Cancela una operación ya cobrada, referenciada por el identificador interbancario
        (no por la referencia corta de conciliación)."""
        raise NotImplementedError
