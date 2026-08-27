import type { RepoAplicacion } from "../../domain/ports/repo-aplicacion";
import type { AplicacionItemDTO, CreateAplicacionDTO } from "../dtos/aplicacion-dto";

export async function createAplicacion(
  repo: RepoAplicacion,
  dto: CreateAplicacionDTO,
): Promise<AplicacionItemDTO> {
  const entity = await repo.create(dto);
  return { id: entity.id, nombre: entity.nombre, dominio: entity.dominio, proveedor: entity.proveedor };
}
