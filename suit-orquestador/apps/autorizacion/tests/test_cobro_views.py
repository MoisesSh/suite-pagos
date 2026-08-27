import uuid
from unittest.mock import patch

from apps.autorizacion.application.services import CheckoutTokenService
from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import (
    AplicacionProveedorPermitido,
    AplicacionRegistrada,
    DominioPermitido,
    IdempotencyKey,
    IntencionPago,
    MedioPago,
    ProveedorPago,
)
from apps.autorizacion.domain.puertos_pago import ResultadoCobro, ResultadoOtp
from apps.autorizacion.tests.base import BaseAPITestCase

COBRO_BODY_BASE = {
    'proveedor': 'BDV',
    'cedula_pagador': 'V12345678',
    'telefono_pagador': '04125692243',
    'banco_codigo': '0102',
    'otp': '5551111',
}


class _ConCatalogoYToken(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        # get_or_create: catálogos ya poblados por la migración de seed 0004 (Bloque #3).
        self.medio_pago, _ = MedioPago.objects.get_or_create(codigo='C2P', defaults={'nombre': 'Pago Móvil C2P'})
        self.proveedor, _ = ProveedorPago.objects.get_or_create(
            codigo='BDV', defaults={'medio_pago': self.medio_pago, 'nombre': 'Banco de Venezuela'},
        )
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())
        DominioPermitido.objects.create(aplicacion=self.aplicacion, dominio='conatel.gob.ve')
        AplicacionProveedorPermitido.objects.create(aplicacion=self.aplicacion, proveedor=self.proveedor)
        # monto/moneda quedan atados acá — es la fuente de verdad para /cobro/, el
        # body del submit no los acepta (ver EjecutarCobroRequestSerializer).
        self.checkout_token = CheckoutTokenService.generar(
            aplicacion_id=self.aplicacion.id, proveedor_codigo='BDV', monto='1000.60', moneda='VES',
        )


class SolicitarOtpViewTests(_ConCatalogoYToken):
    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_otp_exitoso(self, MockAdapter):
        MockAdapter.return_value.generar_otp.return_value = ResultadoOtp(
            codigo='1000', mensaje='Proceso finalizado', payload_crudo={},
        )

        response = self.client.post('/api/autorizacion/cobro/otp/', {
            'checkout_token': self.checkout_token, 'proveedor': 'BDV', 'cedula_pagador': 'V12345678',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['resultado'], 'otp_enviado')

    def test_checkout_token_invalido_responde_401(self):
        response = self.client.post('/api/autorizacion/cobro/otp/', {
            'checkout_token': 'token-basura', 'proveedor': 'BDV', 'cedula_pagador': 'V12345678',
        })
        self.assertEqual(response.status_code, 401)

    def test_proveedor_no_coincide_con_token_responde_403(self):
        response = self.client.post('/api/autorizacion/cobro/otp/', {
            'checkout_token': self.checkout_token, 'proveedor': 'OTRO', 'cedula_pagador': 'V12345678',
        })
        self.assertEqual(response.status_code, 403)

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_proveedor_rechaza_otp_responde_400(self, MockAdapter):
        MockAdapter.return_value.generar_otp.side_effect = ProveedorPagoError(codigo='1080', mensaje='Documento inválido')

        response = self.client.post('/api/autorizacion/cobro/otp/', {
            'checkout_token': self.checkout_token, 'proveedor': 'BDV', 'cedula_pagador': 'invalido',
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codigo_proveedor'], '1080')

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_proveedor_no_disponible_responde_503(self, MockAdapter):
        MockAdapter.return_value.generar_otp.side_effect = ProveedorPagoIndisponibleError('timeout')

        response = self.client.post('/api/autorizacion/cobro/otp/', {
            'checkout_token': self.checkout_token, 'proveedor': 'BDV', 'cedula_pagador': 'V12345678',
        })
        self.assertEqual(response.status_code, 503)


class EjecutarCobroViewTests(_ConCatalogoYToken):
    def _resultado_cobro_exitoso(self):
        return ResultadoCobro(
            codigo='1000', mensaje='Proceso finalizado',
            referencia_corta='090037579602',
            identificador_interbancario='0102010298400079090940416589264220251114162931090620472770',
            payload_crudo={'code': '1000'},
        )

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_cobro_exitoso_crea_pago_capturado(self, MockAdapter):
        MockAdapter.return_value.procesar_cobro.return_value = self._resultado_cobro_exitoso()
        body = {**COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': str(uuid.uuid4())}

        response = self.client.post('/api/autorizacion/cobro/', body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], IntencionPago.EstadoPago.CAPTURADO)
        self.assertEqual(response.data['referencia_corta'], '090037579602')
        pago = IntencionPago.objects.get(id=response.data['pago_id'])
        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.CAPTURADO)

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_reintento_con_misma_idempotency_key_no_vuelve_a_llamar_al_proveedor(self, MockAdapter):
        MockAdapter.return_value.procesar_cobro.return_value = self._resultado_cobro_exitoso()
        idem_key = str(uuid.uuid4())
        body = {**COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': idem_key}

        primera = self.client.post('/api/autorizacion/cobro/', body)
        segunda = self.client.post('/api/autorizacion/cobro/', body)

        self.assertEqual(primera.data, segunda.data)
        self.assertEqual(MockAdapter.return_value.procesar_cobro.call_count, 1)
        self.assertEqual(IntencionPago.objects.count(), 1)

    def test_idempotency_key_con_payload_distinto_responde_409(self):
        idem_key = str(uuid.uuid4())
        body1 = {**COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': idem_key}
        body2 = {
            **COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': idem_key,
            'telefono_pagador': '04129999999',
        }

        with patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter') as MockAdapter:
            MockAdapter.return_value.procesar_cobro.return_value = self._resultado_cobro_exitoso()
            self.client.post('/api/autorizacion/cobro/', body1)
            response = self.client.post('/api/autorizacion/cobro/', body2)

        self.assertEqual(response.status_code, 409)

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_monto_del_body_se_ignora_se_usa_el_del_checkout_token(self, MockAdapter):
        """Vector de fraude cerrado: el OTP autentica al pagador, no valida el monto.
        Un 'monto' inyectado en el body del submit (ej. editando la URL/request del
        iframe) no debe tener ningún efecto — el monto real cobrado es siempre el
        atado criptográficamente al checkout_token."""
        adaptador_mock = MockAdapter.return_value
        adaptador_mock.procesar_cobro.return_value = self._resultado_cobro_exitoso()
        body = {
            **COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': str(uuid.uuid4()),
            'monto': '1.00', 'moneda': 'USD',  # ignorados por el serializer — ni siquiera son campos válidos
        }

        response = self.client.post('/api/autorizacion/cobro/', body)

        self.assertEqual(response.status_code, 200)
        pago = IntencionPago.objects.get(id=response.data['pago_id'])
        self.assertEqual(str(pago.monto), '1000.60')
        self.assertEqual(pago.moneda.codigo, 'VES')
        monto_enviado_al_proveedor = adaptador_mock.procesar_cobro.call_args.kwargs['monto']
        self.assertEqual(monto_enviado_al_proveedor, pago.monto)

    def test_checkout_token_invalido_responde_401(self):
        body = {**COBRO_BODY_BASE, 'checkout_token': 'token-basura', 'idempotency_key': str(uuid.uuid4())}
        response = self.client.post('/api/autorizacion/cobro/', body)
        self.assertEqual(response.status_code, 401)

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_proveedor_rechaza_cobro_por_saldo_insuficiente_responde_402_y_marca_rechazado(self, MockAdapter):
        MockAdapter.return_value.procesar_cobro.side_effect = ProveedorPagoError(codigo='1034', mensaje='Saldo insuficiente')
        idem_key = str(uuid.uuid4())
        body = {**COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': idem_key}

        response = self.client.post('/api/autorizacion/cobro/', body)

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data['codigo_proveedor'], '1034')
        idem = IdempotencyKey.objects.get(key=idem_key)
        self.assertEqual(idem.estado, IdempotencyKey.Estado.RECHAZADO)

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_proveedor_no_disponible_no_marca_idempotency_key_permite_reintento(self, MockAdapter):
        MockAdapter.return_value.procesar_cobro.side_effect = ProveedorPagoIndisponibleError('timeout')
        idem_key = str(uuid.uuid4())
        body = {**COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': idem_key}

        response = self.client.post('/api/autorizacion/cobro/', body)

        self.assertEqual(response.status_code, 503)
        idem = IdempotencyKey.objects.get(key=idem_key)
        self.assertEqual(idem.estado, IdempotencyKey.Estado.PENDIENTE)
        # el IntencionPago quedó creado (pendiente) — un reintento legítimo lo reusa en vez
        # de crear uno nuevo (OneToOneField IdempotencyKey.intencion_pago).
        self.assertEqual(IntencionPago.objects.filter(idempotency_key=idem).count(), 1)

    @patch('apps.autorizacion.api.views.BDVPagoMovilC2PAdapter')
    def test_reintento_tras_falla_de_transporte_reusa_el_mismo_pago(self, MockAdapter):
        idem_key = str(uuid.uuid4())
        body = {**COBRO_BODY_BASE, 'checkout_token': self.checkout_token, 'idempotency_key': idem_key}

        MockAdapter.return_value.procesar_cobro.side_effect = ProveedorPagoIndisponibleError('timeout')
        self.client.post('/api/autorizacion/cobro/', body)

        MockAdapter.return_value.procesar_cobro.side_effect = None
        MockAdapter.return_value.procesar_cobro.return_value = self._resultado_cobro_exitoso()
        response = self.client.post('/api/autorizacion/cobro/', body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(IntencionPago.objects.count(), 1)
