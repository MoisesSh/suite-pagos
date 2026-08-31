import type { RepoDiscrepancia } from "../../domain/ports/repo-discrepancia";
import type { DiscrepanciaItemDTO, ResolverDiscrepanciaDTO } from "../dtos/discrepancia-dto";
import { toDiscrepanciaItemDTO } from "./list-discrepancias";

export async function resolverDiscrepancia(
  repo: RepoDiscrepancia,
  id: string,
  dto: ResolverDiscrepanciaDTO,
): Promise<DiscrepanciaItemDTO> {
  const entity = await repo.resolver(id, dto);
  return toDiscrepanciaItemDTO(entity);
}
