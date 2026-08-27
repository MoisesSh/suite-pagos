from django.db import migrations

# Fuerza estructuralmente en Postgres que TransicionEstadoPago solo pueda insertar
# transiciones válidas — no solo disciplina de servicio (db-plan-pagos.md 2.2,
# decisión de negocio confirmada por el usuario). Valida dos cosas:
#   1. Que (estado_anterior, estado_nuevo) sea un par permitido por la máquina de
#      estados (authorize -> capture -> void/refund, con fallo/expiración).
#   2. Que estado_anterior coincida con el último estado_nuevo real registrado
#      para ese pago (evita insertar una transición fuera de secuencia) — esto
#      requiere consultar otras filas, por lo que un simple CheckConstraint no
#      alcanza y hace falta un trigger.
#
# Solo aplica sobre Postgres (PL/pgSQL). En sqlite (desarrollo local sin DB_*
# seteadas, ver settings.py) esta migración es un no-op: la validez de las
# transiciones NO queda forzada a nivel de motor, solo por disciplina de la
# capa de aplicación, hasta que se corra sobre Postgres real.

CREATE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION autorizacion_validar_transicion_estado_pago()
RETURNS TRIGGER AS $$
DECLARE
    estado_previo_real varchar;
BEGIN
    SELECT estado_nuevo INTO estado_previo_real
    FROM autorizacion_transicionestadopago
    WHERE pago_id = NEW.pago_id
    ORDER BY created_at DESC, id DESC
    LIMIT 1;

    IF estado_previo_real IS DISTINCT FROM NEW.estado_anterior THEN
        RAISE EXCEPTION
            'estado_anterior (%) no coincide con el último estado real (%) del pago %',
            NEW.estado_anterior, estado_previo_real, NEW.pago_id;
    END IF;

    IF NEW.estado_anterior IS NULL THEN
        IF NEW.estado_nuevo <> 'pendiente' THEN
            RAISE EXCEPTION
                'La primera transición de un pago debe ser a pendiente (recibido %)', NEW.estado_nuevo;
        END IF;
        RETURN NEW;
    END IF;

    IF NOT (
        (NEW.estado_anterior = 'pendiente'  AND NEW.estado_nuevo IN ('autorizado', 'fallido', 'expirado')) OR
        (NEW.estado_anterior = 'autorizado' AND NEW.estado_nuevo IN ('capturado', 'anulado', 'fallido', 'expirado')) OR
        (NEW.estado_anterior = 'capturado'  AND NEW.estado_nuevo = 'reembolsado')
    ) THEN
        RAISE EXCEPTION 'Transición de estado inválida: % -> %', NEW.estado_anterior, NEW.estado_nuevo;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

DROP_FUNCTION_SQL = """
DROP FUNCTION IF EXISTS autorizacion_validar_transicion_estado_pago() CASCADE;
"""

CREATE_TRIGGER_SQL = """
CREATE TRIGGER trg_validar_transicion_estado_pago
BEFORE INSERT ON autorizacion_transicionestadopago
FOR EACH ROW EXECUTE FUNCTION autorizacion_validar_transicion_estado_pago();
"""

DROP_TRIGGER_SQL = """
DROP TRIGGER IF EXISTS trg_validar_transicion_estado_pago ON autorizacion_transicionestadopago;
"""


def crear_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(CREATE_FUNCTION_SQL)
        cursor.execute(CREATE_TRIGGER_SQL)


def eliminar_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(DROP_TRIGGER_SQL)
        cursor.execute(DROP_FUNCTION_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('autorizacion', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_trigger, eliminar_trigger),
    ]
