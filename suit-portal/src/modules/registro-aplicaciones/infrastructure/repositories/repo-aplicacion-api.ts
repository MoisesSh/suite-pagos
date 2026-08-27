import type { RepoAplicacion } from "../../domain/ports/repo-aplicacion";
import { postAplicacion } from "../http/aplicaciones-api";

export const repoAplicacionApi: RepoAplicacion = {
  create: postAplicacion,
};
