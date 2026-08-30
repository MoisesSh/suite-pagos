import type { RepoAplicacion } from "../../domain/ports/repo-aplicacion";

export async function activarAplicacion(
  repo: RepoAplicacion,
  id: string,
  activa: boolean,
): Promise<void> {
  await repo.activarDesactivar(id, activa);
}
