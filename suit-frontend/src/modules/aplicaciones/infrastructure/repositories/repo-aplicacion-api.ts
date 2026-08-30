import type { RepoAplicacion } from "../../domain/ports/repo-aplicacion";
import { getAplicaciones, patchAplicacionActiva, postAplicacion } from "../http/aplicaciones-api";

export const repoAplicacionApi: RepoAplicacion = {
  getAll: getAplicaciones,
  create: postAplicacion,
  activarDesactivar: patchAplicacionActiva,
};
