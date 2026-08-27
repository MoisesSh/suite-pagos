from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.conciliacion.application.services.matching import MatchingService
from apps.conciliacion.domain import bdv
from apps.conciliacion.domain.models import ConsultaConciliacionProveedor as CCP
from apps.conciliacion.domain.models import Discrepancia
from apps.shared.tests import factories


class InterpretarRespuestaConciliacionTests(SimpleTestCase):
    """Contrato real de BDV `getMovement/v2` (investigaciones/research-brief-pagos.md §4.2):
    solo dos códigos binarios, `1010` agrupa 4 escenarios distinguibles solo por `message`."""

    def test_codigo_exito_es_conciliado(self):
        resultado = bdv.interpretar_respuesta_conciliacion(
            '1000', 'Monto: 120.00 - estatus: Transacción realizada',
        )
        self.assertEqual(resultado, CCP.ResultadoInterpretado.CONCILIADO)

    def test_registro_no_existe_es_no_encontrado(self):
        resultado = bdv.interpretar_respuesta_conciliacion(
            '1010', 'No se pudo validar el movimiento : Registro solicitado no existe',
        )
        self.assertEqual(resultado, CCP.ResultadoInterpretado.NO_ENCONTRADO)

    def test_ya_conciliado_anteriormente(self):
        resultado = bdv.interpretar_respuesta_conciliacion(
            '1010',
            'Pago Móvil procesado exitosamente en el BDV. El movimiento ya fue conciliado anteriormente.',
        )
        self.assertEqual(resultado, CCP.ResultadoInterpretado.YA_CONCILIADO)

    def test_error_credenciales_no_afiliado(self):
        resultado = bdv.interpretar_respuesta_conciliacion('1010', 'Cliente no afiliado al producto')
        self.assertEqual(resultado, CCP.ResultadoInterpretado.ERROR_CREDENCIALES)

    def test_monto_no_coincide(self):
        resultado = bdv.interpretar_respuesta_conciliacion(
            '1010', 'monto : 150.00 - estatus : Transacción realizada',
        )
        self.assertEqual(resultado, CCP.ResultadoInterpretado.MONTO_NO_COINCIDE)

    def test_mensaje_no_documentado_cae_en_pendiente_revision(self):
        """Nunca falla en silencio: cualquier wording nuevo del proveedor (ya
        cambió entre versiones, ver §4.2) debe quedar en revisión manual, no perderse."""
        resultado = bdv.interpretar_respuesta_conciliacion('1010', 'algo que el banco nunca documentó')
        self.assertEqual(resultado, CCP.ResultadoInterpretado.PENDIENTE_REVISION)

    def test_codigo_entero_se_normaliza_a_string(self):
        resultado = bdv.interpretar_respuesta_conciliacion(1000, 'Monto: 120.00 - estatus: Transacción realizada')
        self.assertEqual(resultado, CCP.ResultadoInterpretado.CONCILIADO)


class EsOperacionIntrabancoBdvTests(SimpleTestCase):
    def test_mismo_banco_es_intrabanco(self):
        self.assertTrue(bdv.es_operacion_intrabanco_bdv('0102'))

    def test_banco_distinto_no_es_intrabanco(self):
        self.assertFalse(bdv.es_operacion_intrabanco_bdv('0134'))

    def test_requiere_cedula_estricta_solo_en_intrabanco(self):
        self.assertTrue(bdv.requiere_cedula_estricta('0102'))
        self.assertFalse(bdv.requiere_cedula_estricta('0134'))


class ProcesarRespuestaBdvTests(TestCase):
    def setUp(self):
        self.evento = factories.crear_evento_pago()
        self.banco_bdv = factories.crear_banco(codigo='0102', nombre='Banco de Venezuela')

    @staticmethod
    def _respuesta(code, message, data=None):
        return {'code': code, 'message': message, 'data': data, 'status': 200}

    def _procesar(self, banco, respuesta, **overrides):
        datos = {
            'evento': self.evento,
            'banco': banco,
            'referencia_corta': '12345678',
            'telefono_pagador': '04127141363',
            'cedula_pagador': 'V27037606',
            'importe_esperado': Decimal('120.00'),
            'fecha_pago': timezone.now(),
            'respuesta_cruda': respuesta,
        }
        datos.update(overrides)
        return MatchingService.procesar_respuesta_bdv(**datos)

    def test_respuesta_exitosa_no_genera_discrepancia(self):
        respuesta = self._respuesta(1000, 'Monto: 120.00 - estatus: Transacción realizada', {
            'status': '1000', 'amount': '120.00', 'reason': 'Transacción realizada', 'referencia': '12345678',
        })
        consulta = self._procesar(self.banco_bdv, respuesta)

        self.assertEqual(consulta.resultado_interpretado, CCP.ResultadoInterpretado.CONCILIADO)
        self.assertFalse(Discrepancia.objects.filter(consulta=consulta).exists())

    def test_no_encontrado_genera_discrepancia_sin_movimiento_bancario(self):
        respuesta = self._respuesta(1010, 'No se pudo validar el movimiento : Registro solicitado no existe')
        consulta = self._procesar(self.banco_bdv, respuesta)

        discrepancia = Discrepancia.objects.get(consulta=consulta)
        self.assertEqual(discrepancia.tipo, Discrepancia.Tipo.SIN_MOVIMIENTO_BANCARIO)
        self.assertEqual(discrepancia.severidad, Discrepancia.Severidad.MEDIA)
        self.assertEqual(discrepancia.estado_resolucion, Discrepancia.EstadoResolucion.ABIERTA)
        self.assertEqual(discrepancia.evento, self.evento)

    def test_monto_no_coincide_genera_discrepancia_alta(self):
        respuesta = self._respuesta(1010, 'monto : 150.00 - estatus : Transacción realizada')
        consulta = self._procesar(self.banco_bdv, respuesta)

        discrepancia = Discrepancia.objects.get(consulta=consulta)
        self.assertEqual(discrepancia.tipo, Discrepancia.Tipo.MONTO_NO_COINCIDE)
        self.assertEqual(discrepancia.severidad, Discrepancia.Severidad.ALTA)

    def test_error_credenciales_genera_discrepancia_critica(self):
        respuesta = self._respuesta(1010, 'Cliente no afiliado al producto')
        consulta = self._procesar(self.banco_bdv, respuesta)

        discrepancia = Discrepancia.objects.get(consulta=consulta)
        self.assertEqual(discrepancia.tipo, Discrepancia.Tipo.ERROR_PROVEEDOR)
        self.assertEqual(discrepancia.severidad, Discrepancia.Severidad.CRITICA)

    def test_ya_conciliado_genera_discrepancia_duplicado(self):
        respuesta = self._respuesta(
            1010,
            'Pago Móvil procesado exitosamente en el BDV. El movimiento ya fue conciliado anteriormente.',
        )
        consulta = self._procesar(self.banco_bdv, respuesta)

        discrepancia = Discrepancia.objects.get(consulta=consulta)
        self.assertEqual(discrepancia.tipo, Discrepancia.Tipo.DUPLICADO)

    def test_cedula_confiable_solo_en_operacion_intrabanco_bdv(self):
        banco_otro = factories.crear_banco(codigo='0134', nombre='Banesco')
        respuesta = self._respuesta(1000, 'Monto: 120.00 - estatus: Transacción realizada', {
            'status': '1000', 'amount': '120.00', 'reason': 'Transacción realizada', 'referencia': '12345678',
        })

        consulta_bdv = self._procesar(self.banco_bdv, respuesta)
        self.assertTrue(consulta_bdv.cedula_confiable)

        consulta_interbancaria = self._procesar(banco_otro, respuesta, referencia_corta='87654321')
        self.assertFalse(consulta_interbancaria.cedula_confiable)
