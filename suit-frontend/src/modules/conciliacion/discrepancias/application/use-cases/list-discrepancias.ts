import type { DiscrepanciasFiltro, RepoDiscrepancia } from "../../domain/ports/repo-discrepancia";
import type { DiscrepanciaEntity } from "../../domain/entities/discrepancia-entity";
import type { DiscrepanciaItemDTO } from "../dtos/discrepancia-dto";

export function toDiscrepanciaItemDTO(entity: DiscrepanciaEntity): DiscrepanciaItemDTO {
  return {
    id: entity.id,
    movimiento: entity.movimiento,
    consulta: entity.consulta,
    evento: entity.evento,
    tipo: entity.tipo,
    severidad: entity.severidad,
    estadoResolucion: entity.estadoResolucion,
    resueltoPor: entity.resueltoPor,
    resueltoAt: entity.resueltoAt,
    notas: entity.notas,
    createdAt: entity.createdAt,
  };
}

export async function listDiscrepancias(
  repo: RepoDiscrepancia,
  filtro: DiscrepanciasFiltro,
): Promise<DiscrepanciaItemDTO[]> {
  const entities = await repo.getAll(filtro);
  return entities.map(toDiscrepanciaItemDTO);
}
