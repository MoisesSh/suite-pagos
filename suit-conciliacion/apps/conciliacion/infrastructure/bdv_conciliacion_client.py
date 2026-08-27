"""Adaptador HTTP real hacia la API de Conciliación de BDV
(`POST /getMovement/v2`), contrato documentado en
investigaciones/research-brief-pagos.md §4.2. Capa de infraestructura pura:
solo hace la llamada y devuelve el JSON crudo — la interpretación de la
respuesta vive en apps/conciliacion/domain/bdv.py, no aquí.

Todavía no está conectado al consumer automático (infrastructure/tasks.py):
falta que suit-orquestador emita `pago.confirmado` con `cedula_pagador`/
`telefono_pagador` en el payload (bloqueante activo, ver conversación con el
coordinador). Se puede llamar ya manualmente o desde un test.
"""

import requests
from django.conf import settings

from apps.conciliacion.domain import bdv


class BdvConciliacionNoDisponible(Exception):
    """La API de Conciliación de BDV no respondió (timeout, red caída, HTTP inesperado)."""


class BdvConciliacionClient:
    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = base_url or settings.BDV_CONCILIACION_BASE_URL
        self.api_key = api_key or settings.BDV_CONCILIACION_API_KEY
        self.timeout = timeout or settings.BDV_CONCILIACION_TIMEOUT

    def consultar_movimiento(
        self, cedula_pagador, telefono_pagador, telefono_destino,
        referencia_corta, fecha_pago, importe, banco_origen_codigo,
    ):
        """`fecha_pago` en formato `AAAA-MM-DD`, `importe` como string decimal
        (`"120.00"`) — mismo formato que espera el proveedor. Devuelve el JSON
        crudo (`code`, `message`, `data`, `status`) tal cual lo entrega BDV."""
        payload = {
            'cedulaPagador': cedula_pagador,
            'telefonoPagador': telefono_pagador,
            'telefonoDestino': telefono_destino,
            'referencia': referencia_corta,
            'fechaPago': fecha_pago,
            'importe': importe,
            'bancoOrigen': banco_origen_codigo,
            'reqCed': bdv.requiere_cedula_estricta(banco_origen_codigo),
        }
        try:
            response = requests.post(
                f'{self.base_url}/getMovement/v2',
                json=payload,
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json',
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BdvConciliacionNoDisponible(
                f'No se pudo consultar getMovement/v2 para referencia {referencia_corta}: {exc}',
            ) from exc

        return response.json()
