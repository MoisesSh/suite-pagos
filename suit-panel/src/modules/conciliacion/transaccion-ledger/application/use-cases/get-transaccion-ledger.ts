import type { RepoTransaccionLedger } from "../../domain/ports/repo-transaccion-ledger";
import type { TransaccionLedgerItemDTO } from "../dtos/transaccion-ledger-dto";

export async function getTransaccionLedger(
  repo: RepoTransaccionLedger,
  id: string,
): Promise<TransaccionLedgerItemDTO | null> {
  const entity = await repo.getById(id);
  if (!entity) return null;

  return {
    id: entity.id,
    referenciaEvento: entity.referenciaEvento,
    createdAt: entity.createdAt,
    lineas: entity.lineas.map((linea) => ({
      id: linea.id,
      cuenta: linea.cuenta,
      tipo: linea.tipo,
      monto: linea.monto,
    })),
  };
}
