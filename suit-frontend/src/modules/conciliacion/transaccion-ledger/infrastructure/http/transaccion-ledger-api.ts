import { apiClient } from "@/shared/infrastructure/http/fetcher-api";
import type { TransaccionLedgerEntity } from "../../domain/entities/transaccion-ledger-entity";
import { mapperTransaccionLedger, type TransaccionLedgerRaw } from "../mappers/mapper-transaccion-ledger";

export async function getTransaccionLedgerById(id: string): Promise<TransaccionLedgerEntity | null> {
  const data = await apiClient.getOrNull<TransaccionLedgerRaw>(`/api/conciliacion/transacciones-ledger/${id}/`);
  return data ? mapperTransaccionLedger(data) : null;
}
