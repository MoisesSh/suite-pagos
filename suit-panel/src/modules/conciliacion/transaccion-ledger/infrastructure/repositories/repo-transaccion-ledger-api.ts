import type { RepoTransaccionLedger } from "../../domain/ports/repo-transaccion-ledger";
import { getTransaccionLedgerById } from "../http/transaccion-ledger-api";

export const repoTransaccionLedgerApi: RepoTransaccionLedger = {
  getById: getTransaccionLedgerById,
};
