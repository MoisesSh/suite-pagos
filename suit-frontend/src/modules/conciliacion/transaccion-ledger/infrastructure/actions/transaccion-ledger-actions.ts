"use server";

import { handleSessionExpired } from "@/shared/infrastructure/http/errors";
import { repoTransaccionLedgerApi } from "../repositories/repo-transaccion-ledger-api";
import { getTransaccionLedger } from "../../application/use-cases/get-transaccion-ledger";
import type { TransaccionLedgerItemDTO } from "../../application/dtos/transaccion-ledger-dto";

export async function fetchTransaccionLedgerAction(id: string): Promise<TransaccionLedgerItemDTO | null> {
  try {
    return await getTransaccionLedger(repoTransaccionLedgerApi, id);
  } catch (error) {
    handleSessionExpired(error);
    throw error;
  }
}
