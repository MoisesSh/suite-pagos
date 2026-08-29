import type { TransaccionLedgerEntity, TipoLinea } from "../../domain/entities/transaccion-ledger-entity";

export interface LineaLedgerRaw {
  id: string;
  cuenta: string;
  tipo: TipoLinea;
  monto: string;
}

export interface TransaccionLedgerRaw {
  id: string;
  referencia_evento: string;
  created_at: string;
  lineas: LineaLedgerRaw[];
}

export function mapperTransaccionLedger(raw: TransaccionLedgerRaw): TransaccionLedgerEntity {
  return {
    id: raw.id,
    referenciaEvento: raw.referencia_evento,
    createdAt: raw.created_at,
    lineas: raw.lineas.map((linea) => ({
      id: linea.id,
      cuenta: linea.cuenta,
      tipo: linea.tipo,
      monto: linea.monto,
    })),
  };
}
