from django.db import transaction


class MatchingService:
    """Interpreta el resultado de una consulta de conciliación (BDV `getMovement/v2` u
    otro proveedor) y genera la `Discrepancia` correspondiente cuando el resultado no
    es un match limpio. Nunca falla en silencio: todo resultado distinto de
    `conciliado` queda registrado como discrepancia (ver db-plan-pagos.md §3.4)."""

    # Bloque #21 (PLAN-DE-MEJORAS.md): plan de cuentas definido por el usuario.
    # Conatel es destinatario final del dinero (no hay liquidación pendiente hacia
    # la app afiliada) — una sola cuenta genérica de terceros para todos los
    # pagadores, sin trazabilidad contable por pagador individual. Sembradas en
    # la migración 0008_seed_cuentas_ledger.py.
    CODIGO_CUENTA_DEBITO_TERCEROS = 'CXC-TERCEROS'
    CODIGO_CUENTA_CREDITO_CONATEL = 'ING-COBRO-TERCEROS'

    # resultado_interpretado -> tipo de Discrepancia (None = no genera discrepancia)
    _MAPA_DISCREPANCIA = None

    @classmethod
    def _mapa_discrepancia(cls):
        from apps.conciliacion.domain.models import ConsultaConciliacionProveedor as CCP
        from apps.conciliacion.domain.models import Discrepancia

        if cls._MAPA_DISCREPANCIA is None:
            cls._MAPA_DISCREPANCIA = {
                CCP.ResultadoInterpretado.NO_ENCONTRADO: (
                    Discrepancia.Tipo.SIN_MOVIMIENTO_BANCARIO, Discrepancia.Severidad.MEDIA,
                ),
                CCP.ResultadoInterpretado.MONTO_NO_COINCIDE: (
                    Discrepancia.Tipo.MONTO_NO_COINCIDE, Discrepancia.Severidad.ALTA,
                ),
                CCP.ResultadoInterpretado.YA_CONCILIADO: (
                    Discrepancia.Tipo.DUPLICADO, Discrepancia.Severidad.MEDIA,
                ),
                CCP.ResultadoInterpretado.ERROR_CREDENCIALES: (
                    Discrepancia.Tipo.ERROR_PROVEEDOR, Discrepancia.Severidad.CRITICA,
                ),
                CCP.ResultadoInterpretado.PENDIENTE_REVISION: (
                    Discrepancia.Tipo.PENDIENTE_REVISION_MANUAL, Discrepancia.Severidad.BAJA,
                ),
            }
        return cls._MAPA_DISCREPANCIA

    @classmethod
    @transaction.atomic
    def procesar_respuesta_bdv(
        cls, evento, banco, referencia_corta, telefono_pagador, cedula_pagador,
        importe_esperado, fecha_pago, respuesta_cruda,
    ):
        """Normaliza la respuesta cruda de `POST /getMovement/v2` (BDV) y registra
        la consulta + discrepancia si aplica. `banco` es el `Banco` origen del
        pagador (`bancoOrigen` del request) — determina si la operación es
        BDV↔BDV (cédula confiable) o interbancaria vía Suiche 7B (no confiable),
        ver `domain/bdv.py`. La llamada HTTP a BDV en sí (armar `respuesta_cruda`)
        es responsabilidad de una futura capa de infraestructura, no de este
        service."""
        from apps.conciliacion.domain import bdv

        codigo_respuesta_raw = str(respuesta_cruda.get('code', ''))
        mensaje_respuesta_raw = respuesta_cruda.get('message', '')

        datos = {
            'referencia_corta': referencia_corta,
            'telefono_pagador': telefono_pagador,
            'cedula_pagador': cedula_pagador or '',
            'cedula_confiable': bdv.es_operacion_intrabanco_bdv(banco.codigo),
            'importe_esperado': importe_esperado,
            'fecha_pago': fecha_pago,
            'codigo_respuesta_raw': codigo_respuesta_raw,
            'mensaje_respuesta_raw': mensaje_respuesta_raw,
            'resultado_interpretado': bdv.interpretar_respuesta_conciliacion(
                codigo_respuesta_raw, mensaje_respuesta_raw,
            ),
            'payload_crudo': respuesta_cruda,
        }
        return cls.registrar_resultado_consulta(evento, banco, datos)

    @classmethod
    @transaction.atomic
    def registrar_resultado_consulta(cls, evento, banco, datos):
        """`datos` es el resultado ya normalizado de consultar al proveedor:
        referencia_corta, telefono_pagador, cedula_pagador, cedula_confiable,
        importe_esperado, fecha_pago, codigo_respuesta_raw, mensaje_respuesta_raw,
        resultado_interpretado, payload_crudo."""
        from apps.conciliacion.domain.models import ConsultaConciliacionProveedor, Discrepancia

        consulta = ConsultaConciliacionProveedor.objects.create(evento=evento, banco=banco, **datos)

        if consulta.resultado_interpretado == ConsultaConciliacionProveedor.ResultadoInterpretado.CONCILIADO:
            cls._registrar_ledger_conciliado(evento, consulta)
        else:
            mapa = cls._mapa_discrepancia()
            entrada = mapa.get(consulta.resultado_interpretado)
            if entrada is not None:
                tipo, severidad = entrada
                Discrepancia.objects.create(
                    consulta=consulta,
                    evento=evento,
                    tipo=tipo,
                    severidad=severidad,
                    estado_resolucion=Discrepancia.EstadoResolucion.ABIERTA,
                )

        return consulta

    @classmethod
    def _registrar_ledger_conciliado(cls, evento, consulta):
        """Asiento de doble entrada de un cobro conciliado (Bloque #21). Débito a la
        cuenta genérica de terceros (dinero del pagador de la app afiliada), crédito a
        la cuenta de ingresos propios de Conatel — destinatario final del dinero, no una
        liquidación pendiente hacia la app afiliada."""
        from apps.conciliacion.application.services.ledger import LedgerService
        from apps.conciliacion.domain.models import CuentaContable, LineaLedger

        cuenta_debito = CuentaContable.objects.get(codigo=cls.CODIGO_CUENTA_DEBITO_TERCEROS)
        cuenta_credito = CuentaContable.objects.get(codigo=cls.CODIGO_CUENTA_CREDITO_CONATEL)
        lineas = [
            {'cuenta': cuenta_debito, 'tipo': LineaLedger.Tipo.DEBITO, 'monto': consulta.importe_esperado},
            {'cuenta': cuenta_credito, 'tipo': LineaLedger.Tipo.CREDITO, 'monto': consulta.importe_esperado},
        ]
        LedgerService.registrar_transaccion(evento, lineas)

    @staticmethod
    @transaction.atomic
    def resolver_discrepancia(discrepancia, usuario, estado_resolucion, notas=''):
        from django.utils import timezone

        discrepancia.estado_resolucion = estado_resolucion
        discrepancia.resuelto_por = usuario
        discrepancia.resuelto_at = timezone.now()
        if notas:
            discrepancia.notas = notas
        discrepancia.save(update_fields=[
            'estado_resolucion', 'resuelto_por', 'resuelto_at', 'notas', 'updated_at',
        ])
        return discrepancia
