import uuid
from decimal import Decimal
from unittest.mock import Mock

from apps.autorizacion.application.services import FlujoCobroC2PService
from apps.autorizacion.domain.errores_proveedor import ProveedorPagoError, ProveedorPagoIndisponibleError
from apps.autorizacion.domain.models import AplicacionRegistrada, Autorizacion, Captura, EventoOutbox, IntencionPago
from apps.autorizacion.domain.puertos_pago import PaymentProviderPort, ResultadoCobro, ResultadoOtp
from apps.autorizacion.tests.base import BaseAPITestCase


class FlujoCobroC2PServiceTests(BaseAPITestCase):
    """Mockea el adaptador (PaymentProviderPort) en el punto de entrada del service — no
    toca BDV, ni siquiera el ambiente QA, desde el test suite."""

    def setUp(self):
        super().setUp()
        self.aplicacion = AplicacionRegistrada.objects.create(nombre='Conatel en Línea', app_origen_id=uuid.uuid4())

    def test_iniciar_crea_intencion_pago_pendiente(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')

        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.PENDIENTE)
        self.assertEqual(pago.moneda.codigo, 'VES')
        self.assertEqual(pago.transiciones.count(), 1)

    def test_ejecutar_cobro_exitoso_crea_autorizacion_y_captura_transiciona_a_capturado(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')
        adaptador = Mock(spec=PaymentProviderPort)
        adaptador.procesar_cobro.return_value = ResultadoCobro(
            codigo='1000', mensaje='Proceso finalizado',
            referencia_corta='090037579602',
            identificador_interbancario='0102010298400079090940416589264220251114162931090620472770',
            payload_crudo={'code': '1000'},
        )

        autorizacion, captura = FlujoCobroC2PService.ejecutar_cobro(
            pago, adaptador=adaptador, cedula_pagador='V12345678', telefono_pagador='04125692243',
            banco_codigo='0102', concepto='Pago', otp='5551111', telefono_comercio='04140282647',
        )

        pago.refresh_from_db()
        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.CAPTURADO)
        self.assertEqual([t.estado_nuevo for t in pago.transiciones.order_by('created_at')],
                          ['pendiente', 'autorizado', 'capturado'])
        self.assertEqual(Autorizacion.objects.filter(pago=pago).count(), 1)
        self.assertEqual(Captura.objects.filter(pago=pago).count(), 1)
        self.assertEqual(autorizacion.identificador_interbancario, captura.identificador_interbancario)
        self.assertIsNotNone(autorizacion.otp_solicitado_at)

    def test_ejecutar_cobro_fallido_transiciona_a_fallido_y_propaga_error(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')
        adaptador = Mock(spec=PaymentProviderPort)
        adaptador.procesar_cobro.side_effect = ProveedorPagoError(codigo='1034', mensaje='Saldo insuficiente')

        with self.assertRaises(ProveedorPagoError):
            FlujoCobroC2PService.ejecutar_cobro(
                pago, adaptador=adaptador, cedula_pagador='V12345678', telefono_pagador='04125692243',
                banco_codigo='0102', concepto='Pago', otp='5551111', telefono_comercio='04140282647',
            )

        pago.refresh_from_db()
        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.FALLIDO)
        self.assertEqual(Autorizacion.objects.filter(pago=pago).count(), 0)
        self.assertEqual(Captura.objects.filter(pago=pago).count(), 0)

    def test_ejecutar_cobro_exitoso_publica_evento_outbox_pago_confirmado(self):
        # investigaciones/contrato-evento-pago-confirmado.md — CERRADO v1.
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')
        adaptador = Mock(spec=PaymentProviderPort)
        adaptador.procesar_cobro.return_value = ResultadoCobro(
            codigo='1000', mensaje='Proceso finalizado',
            referencia_corta='090037579602',
            identificador_interbancario='0102010298400079090940416589264220251114162931090620472770',
            payload_crudo={
                'code': '1000', 'message': 'Proceso finalizado',
                'data': {'date': '2025-11-14', 'endToEndId': '...', 'referencia': '090037579602'},
                'status': 200,
            },
        )

        _autorizacion, captura = FlujoCobroC2PService.ejecutar_cobro(
            pago, adaptador=adaptador, cedula_pagador='V12345678', telefono_pagador='04125692243',
            banco_codigo='0102', concepto='Pago', otp='5551111', telefono_comercio='04140282647',
        )

        eventos = EventoOutbox.objects.filter(pago=pago)
        self.assertEqual(eventos.count(), 1)
        evento = eventos.first()
        self.assertEqual(evento.event_type, 'pago.confirmado')
        self.assertEqual(evento.schema_version, 1)
        self.assertEqual(evento.estado, EventoOutbox.Estado.PENDIENTE)

        payload = evento.payload
        self.assertEqual(payload['pago_id'], str(pago.id))
        self.assertEqual(payload['aplicacion_id'], str(self.aplicacion.id))
        self.assertEqual(payload['proveedor_codigo'], 'BDV')
        self.assertEqual(payload['medio_pago_codigo'], 'C2P')
        self.assertEqual(payload['monto'], '1000.60')
        self.assertEqual(payload['moneda_codigo'], 'VES')
        self.assertEqual(payload['cedula_pagador'], 'V12345678')
        self.assertEqual(payload['telefono_pagador'], '04125692243')
        self.assertEqual(payload['banco_pagador_codigo'], '0102')
        self.assertEqual(payload['telefono_comercio'], '04140282647')
        self.assertEqual(payload['referencia_corta'], '090037579602')
        self.assertEqual(payload['identificador_interbancario'], captura.identificador_interbancario)
        self.assertEqual(payload['codigo_respuesta_proveedor'], '1000')
        self.assertEqual(payload['fecha_pago'], '2025-11-14')
        self.assertEqual(payload['capturado_at'], captura.created_at.isoformat())
        self.assertEqual(payload['estado'], IntencionPago.EstadoPago.CAPTURADO)
        self.assertEqual(payload['routing_flag'], IntencionPago.RoutingFlag.LEGACY)
        self.assertEqual(payload['payload_crudo_captura'], captura.payload_crudo)

    def test_ejecutar_cobro_fallido_no_publica_evento_outbox(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')
        adaptador = Mock(spec=PaymentProviderPort)
        adaptador.procesar_cobro.side_effect = ProveedorPagoError(codigo='1034', mensaje='Saldo insuficiente')

        with self.assertRaises(ProveedorPagoError):
            FlujoCobroC2PService.ejecutar_cobro(
                pago, adaptador=adaptador, cedula_pagador='V12345678', telefono_pagador='04125692243',
                banco_codigo='0102', concepto='Pago', otp='5551111', telefono_comercio='04140282647',
            )

        self.assertEqual(EventoOutbox.objects.filter(pago=pago).count(), 0)

    def test_ejecutar_cobro_indisponible_no_transiciona_permite_reintento(self):
        pago = FlujoCobroC2PService.iniciar(aplicacion=self.aplicacion, monto=Decimal('1000.60'), moneda_codigo='VES')
        adaptador = Mock(spec=PaymentProviderPort)
        adaptador.procesar_cobro.side_effect = ProveedorPagoIndisponibleError('timeout')

        with self.assertRaises(ProveedorPagoIndisponibleError):
            FlujoCobroC2PService.ejecutar_cobro(
                pago, adaptador=adaptador, cedula_pagador='V12345678', telefono_pagador='04125692243',
                banco_codigo='0102', concepto='Pago', otp='5551111', telefono_comercio='04140282647',
            )

        pago.refresh_from_db()
        # Sigue pendiente, no fallido: una falla de transporte no es un resultado terminal
        # del banco — un reintento debe poder llamar ejecutar_cobro de nuevo sobre este
        # mismo pago sin violar la máquina de estados (pendiente -> autorizado sigue siendo
        # una transición válida).
        self.assertEqual(pago.estado_actual, IntencionPago.EstadoPago.PENDIENTE)

    def test_solicitar_otp_delega_al_adaptador_sin_persistir_nada(self):
        adaptador = Mock(spec=PaymentProviderPort)
        adaptador.generar_otp.return_value = ResultadoOtp(codigo='1000', mensaje='Proceso finalizado', payload_crudo={})

        resultado = FlujoCobroC2PService.solicitar_otp(adaptador=adaptador, cedula_pagador='V12345678')

        self.assertEqual(resultado.codigo, '1000')
        adaptador.generar_otp.assert_called_once_with(cedula='V12345678')
