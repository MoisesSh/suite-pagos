from django.db import migrations

# Fuerza a nivel de motor Postgres que cada TransaccionLedger balancee
# (suma débitos == suma créditos) — mismo criterio que el Orquestador aplica
# a sus transiciones de estado (supervision-modelos-bd: invariantes de
# negocio críticas a nivel de motor, no solo en el servicio de aplicación).
# CONSTRAINT TRIGGER DEFERRABLE INITIALLY DEFERRED: se evalúa al COMMIT, no
# por cada INSERT de LineaLedger, para permitir insertar varias líneas
# balanceadas dentro de la misma transacción (LedgerService.registrar_transaccion).

CREATE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION conciliacion_validar_balance_ledger() RETURNS trigger AS $$
DECLARE
    v_transaccion_id uuid;
    v_total_debito numeric(19,2);
    v_total_credito numeric(19,2);
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_transaccion_id := OLD.transaccion_id;
    ELSE
        v_transaccion_id := NEW.transaccion_id;
    END IF;

    SELECT
        COALESCE(SUM(monto) FILTER (WHERE tipo = 'debito'), 0),
        COALESCE(SUM(monto) FILTER (WHERE tipo = 'credito'), 0)
    INTO v_total_debito, v_total_credito
    FROM conciliacion_linea_ledger
    WHERE transaccion_id = v_transaccion_id;

    IF v_total_debito <> v_total_credito THEN
        RAISE EXCEPTION 'TransaccionLedger % no balancea: debito=% credito=%',
            v_transaccion_id, v_total_debito, v_total_credito
            USING ERRCODE = '23514';
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

DROP_FUNCTION_SQL = 'DROP FUNCTION IF EXISTS conciliacion_validar_balance_ledger() CASCADE;'

CREATE_TRIGGER_SQL = """
CREATE CONSTRAINT TRIGGER trg_validar_balance_ledger
AFTER INSERT OR UPDATE OR DELETE ON conciliacion_linea_ledger
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION conciliacion_validar_balance_ledger();
"""

DROP_TRIGGER_SQL = 'DROP TRIGGER IF EXISTS trg_validar_balance_ledger ON conciliacion_linea_ledger;'


def crear_trigger_balance(apps, schema_editor):
    # No-op fuera de Postgres: PL/pgSQL no existe en sqlite. El entorno local
    # de este proyecto corre `manage.py test` contra sqlite (sin CREATEDB en
    # el Postgres real, ver testing-backend-django), así que el invariante de
    # balance-cero solo se verifica a nivel de motor en Postgres real —
    # producción y cualquier entorno con DATABASE_URL apuntando a Postgres.
    if schema_editor.connection.vendor != 'postgresql':
        return
    # params=None (no el default `()`) es obligatorio aquí: con `()`,
    # DatabaseSchemaEditor.execute() de Postgres pasa el SQL por
    # connection.ops.compose_sql()/mogrify de psycopg para "mezclar" params
    # del lado del cliente — y esta versión de psycopg NO colapsa `%%` a `%`
    # (`collapse_double_percent=False`), así que cualquier `%` literal de
    # PL/pgSQL (como en el RAISE EXCEPTION de abajo) rompe con
    # "incomplete placeholder"/"only %s, %b, %t son válidos". Con
    # params=None, Django salta compose_sql por completo y manda el SQL tal
    # cual — confirmado corriendo esta migración contra Postgres real
    # (sqlite nunca la ejerce, por eso pasó desapercibido hasta Docker).
    schema_editor.execute(CREATE_FUNCTION_SQL, params=None)
    schema_editor.execute(CREATE_TRIGGER_SQL, params=None)


def eliminar_trigger_balance(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(DROP_TRIGGER_SQL, params=None)
    schema_editor.execute(DROP_FUNCTION_SQL, params=None)


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(crear_trigger_balance, eliminar_trigger_balance),
    ]
