import type {
  CreateAplicacionParams,
  RepoAplicacion,
} from "../../domain/ports/repo-aplicacion";
import { createAplicacionRegistradaEntity } from "../../domain/entities/aplicacion-registrada-entity";

// TODO(gap #1 CONTRATO-API-ACTUAL.md): reemplazar por un repo real que llame
// POST a suit-orquestador (endpoint de AplicacionRegistrada/DominioPermitido/
// AplicacionProveedorPermitido) cuando ese CRUD exista. Hoy ese registro solo
// se gestiona por Django admin — este repo simula la respuesta para que el
// formulario del portal sea usable mientras tanto.
export const repoAplicacionMock: RepoAplicacion = {
  async create(params: CreateAplicacionParams) {
    await new Promise((resolve) => setTimeout(resolve, 600));
    return createAplicacionRegistradaEntity({
      id: crypto.randomUUID(),
      nombre: params.nombre,
      dominio: params.dominio,
      proveedor: params.proveedor,
    });
  },
};
