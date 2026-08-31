"use server";

import { handleSessionExpired } from "@/shared/infrastructure/http/errors";
import { repoDiscrepanciaApi } from "../repositories/repo-discrepancia-api";
import { listDiscrepancias } from "../../application/use-cases/list-discrepancias";
import { resolverDiscrepancia } from "../../application/use-cases/resolver-discrepancia";
import type { DiscrepanciasFiltro } from "../../domain/ports/repo-discrepancia";
import type { DiscrepanciaItemDTO, ResolverDiscrepanciaDTO } from "../../application/dtos/discrepancia-dto";

export async function fetchDiscrepanciasAction(
  filtro: DiscrepanciasFiltro,
): Promise<DiscrepanciaItemDTO[]> {
  try {
    return await listDiscrepancias(repoDiscrepanciaApi, filtro);
  } catch (error) {
    handleSessionExpired(error);
    throw error;
  }
}

export async function resolverDiscrepanciaAction(
  id: string,
  data: ResolverDiscrepanciaDTO,
): Promise<{ success: string } | { error: string }> {
  try {
    await resolverDiscrepancia(repoDiscrepanciaApi, id, data);
    return { success: "Discrepancia actualizada" };
  } catch (error) {
    handleSessionExpired(error);
    return { error: error instanceof Error ? error.message : "Error al resolver la discrepancia" };
  }
}
