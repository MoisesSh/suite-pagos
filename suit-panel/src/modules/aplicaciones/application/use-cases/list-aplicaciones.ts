import type { RepoAplicacion } from "../../domain/ports/repo-aplicacion";
import type { AplicacionItemDTO } from "../dtos/aplicacion-dto";

export async function listAplicaciones(repo: RepoAplicacion): Promise<AplicacionItemDTO[]> {
  const entities = await repo.getAll();
  return entities.map((entity) => ({
    id: entity.id,
    nombre: entity.nombre,
    appOrigenId: entity.appOrigenId,
    activa: entity.activa,
    createdAt: entity.createdAt,
    dominios: entity.dominios.map((d) => ({ id: d.id, dominio: d.dominio, activo: d.activo })),
    proveedoresAutorizados: entity.proveedoresAutorizados.map((p) => ({
      id: p.id,
      proveedor: p.proveedor,
      activo: p.activo,
      autorizadoEn: p.autorizadoEn,
    })),
  }));
}
