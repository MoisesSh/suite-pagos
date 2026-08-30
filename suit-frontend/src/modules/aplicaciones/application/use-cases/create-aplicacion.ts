import type { RepoAplicacion } from "../../domain/ports/repo-aplicacion";
import type { AplicacionCreadaDTO, CreateAplicacionDTO } from "../dtos/aplicacion-dto";

export async function createAplicacion(
  repo: RepoAplicacion,
  dto: CreateAplicacionDTO,
): Promise<AplicacionCreadaDTO> {
  const entity = await repo.create(dto);
  return { id: entity.id, nombre: entity.nombre, dominio: entity.dominio, proveedor: entity.proveedor };
}
