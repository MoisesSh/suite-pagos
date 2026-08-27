import type { RepoDiscrepancia } from "../../domain/ports/repo-discrepancia";
import { getDiscrepancias, patchDiscrepancia } from "../http/discrepancias-api";

export const repoDiscrepanciaApi: RepoDiscrepancia = {
  getAll: getDiscrepancias,
  resolver: patchDiscrepancia,
};
