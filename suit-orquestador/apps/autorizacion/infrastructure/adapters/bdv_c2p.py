import requests
from django.conf import settings

from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.puertos_pago import PaymentProviderPort, ResultadoAnulacion, ResultadoCobro, ResultadoOtp

RUTA_PAYMENTKEY = '/BankMobilePaymentC2P/MultipleAccounts/paymentkey/v2'
RUTA_PROCESO = '/BankMobilePaymentC2P/MultipleAccounts/process/v2'
RUTA_ANULACION = '/BankMobilePaymentC2P/MultipleAccounts/annulment/v2'

CODIGO_EXITO = '1000'


class BDVPagoMovilC2PAdapter(PaymentProviderPort):
    """Adaptador real del proveedor BDV Pago Móvil C2P (db-plan-pagos.md sección 2.5,
    research-brief-pagos.md sección 4.1, `Doc - API C2P Cuentas Múltiples.pdf`).

    Autenticación por X-API-Key estática (no hay token de sesión que rotar). Toda respuesta
    del proveedor llega con HTTP 200 y el resultado real en el campo `code` del body — este
    adaptador no confía en el status HTTP para distinguir éxito/error de negocio, solo para
    detectar caída de transporte."""

    def __init__(self, base_url=None, api_key=None, timeout=None):
        base_url = base_url or settings.BDV_C2P_BASE_URL
        if not base_url:
            raise RuntimeError(
                'BDV_C2P_BASE_URL no está configurada — sin default al QA real del banco '
                '(evita apuntar por accidente al ambiente del proveedor sin querer).',
            )
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key or settings.BDV_C2P_API_KEY
        self._timeout = timeout or settings.BDV_C2P_TIMEOUT_SEGUNDOS

    def _headers(self):
        return {'X-API-Key': self._api_key, 'Content-Type': 'application/json'}

    def _post(self, ruta, body):
        try:
            response = requests.post(
                f'{self._base_url}{ruta}', json=body, headers=self._headers(), timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ProveedorPagoIndisponibleError(str(exc)) from exc

        data = response.json()
        codigo = str(data.get('code'))
        if codigo != CODIGO_EXITO:
            raise ProveedorPagoError(codigo=codigo, mensaje=data.get('message', ''), payload_crudo=data)
        return data

    def generar_otp(self, *, cedula):
        data = self._post(RUTA_PAYMENTKEY, {'customerDocumentId': cedula})
        return ResultadoOtp(codigo=str(data['code']), mensaje=data['message'], payload_crudo=data)

    def procesar_cobro(
        self, *, cedula, telefono_pagador, monto, banco_codigo, concepto, otp,
        moneda_codigo, tipo_operacion_codigo, telefono_comercio,
    ):
        body = {
            'customerDocumentId': cedula,
            'customerNumberInstrument': telefono_pagador,
            'amount': str(monto),
            'customerBankCode': banco_codigo,
            'concept': concepto,
            'otp': otp,
            'coinType': moneda_codigo,
            'operationType': tipo_operacion_codigo,
            'commerceNumberInstrument': telefono_comercio,
        }
        data = self._post(RUTA_PROCESO, body)
        payload = data.get('data') or {}
        return ResultadoCobro(
            codigo=str(data['code']),
            mensaje=data['message'],
            referencia_corta=payload.get('referencia'),
            identificador_interbancario=payload.get('endToEndId'),
            payload_crudo=data,
        )

    def anular(self, *, identificador_interbancario, referencia_origen=None):
        body = {'endToEndId': identificador_interbancario, 'referenceOrigin': referencia_origen}
        data = self._post(RUTA_ANULACION, body)
        return ResultadoAnulacion(codigo=str(data['code']), mensaje=data['message'], payload_crudo=data)
