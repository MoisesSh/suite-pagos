import type { EventoEntity } from "../../domain/entities/evento-entity";

export interface EventoRaw {
  id: string;
  event_id: string;
  event_type: string;
  schema_version: number;
  procesado_at: string | null;
  created_at: string;
  transaccion_ledger_id: string | null;
}

export function mapperEvento(raw: EventoRaw): EventoEntity {
  return {
    id: raw.id,
    eventId: raw.event_id,
    eventType: raw.event_type,
    schemaVersion: raw.schema_version,
    procesadoAt: raw.procesado_at,
    createdAt: raw.created_at,
    transaccionLedgerId: raw.transaccion_ledger_id,
  };
}
