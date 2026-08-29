import type { TransaccionLedgerEntity } from "../entities/transaccion-ledger-entity";

export interface RepoTransaccionLedger {
  getById(id: string): Promise<TransaccionLedgerEntity | null>;
}
