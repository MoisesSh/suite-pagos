import type { RepoEvento } from "../../domain/ports/repo-evento";
import { getEventos } from "../http/eventos-api";

export const repoEventoApi: RepoEvento = {
  getAll: getEventos,
};
