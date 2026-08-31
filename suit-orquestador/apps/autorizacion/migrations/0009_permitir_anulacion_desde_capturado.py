from django.db import migrations

# C2P es cargo instantáneo (db-plan-pagos.md 2.5): process/v2 hace reserva y cobro en
# una sola llamada, así que un pago real siempre transiciona autorizado -> capturado
# antes de que exista una Anulacion que pedirle a BDV. La regla original (0002)
# permitía anular solo desde 'autorizado', un estado transitorio que un pago C2P real
# nunca deja como terminal — sin este ajuste, ejecutar_cobro/anular_cobro nunca podría
# anular un cobro ya hecho (Bloque #22, hallazgo de bdv_c2p.anular() sin invocar).

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
        (NEW.estado_anterior = 'capturado'  AND NEW.estado_nuevo IN ('anulado', 'reembolsado'))
    ) THEN
        RAISE EXCEPTION 'Transición de estado inválida: % -> %', NEW.estado_anterior, NEW.estado_nuevo;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Restaura exactamente la función de 0002 (sin 'capturado' -> 'anulado').
REVERTIR_FUNCTION_SQL = """
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


def actualizar_funcion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(CREATE_FUNCTION_SQL)


def revertir_funcion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERTIR_FUNCTION_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('autorizacion', '0008_webhook_entrega'),
    ]

    operations = [
        migrations.RunPython(actualizar_funcion, revertir_funcion),
    ]
