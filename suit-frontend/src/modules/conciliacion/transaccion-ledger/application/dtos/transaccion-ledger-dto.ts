import type { TipoLinea } from "../../domain/entities/transaccion-ledger-entity";

export interface LineaLedgerItemDTO {
  id: string;
  cuenta: string;
  tipo: TipoLinea;
  monto: string;
}

export interface TransaccionLedgerItemDTO {
  id: string;
  referenciaEvento: string;
  createdAt: string;
  lineas: LineaLedgerItemDTO[];
}
