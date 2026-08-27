import { apiClient } from "@/shared/infrastructure/http/fetcher-api";
import { queryParams } from "@/shared/infrastructure/http/query-params";
import type { DiscrepanciaEntity } from "../../domain/entities/discrepancia-entity";
import type {
  DiscrepanciasFiltro,
  ResolverDiscrepanciaParams,
} from "../../domain/ports/repo-discrepancia";
import { mapperDiscrepancia, type DiscrepanciaRaw } from "../mappers/mapper-discrepancia";

export async function getDiscrepancias(filtro: DiscrepanciasFiltro): Promise<DiscrepanciaEntity[]> {
  const qs = queryParams({
    estado_resolucion: filtro.estadoResolucion,
    severidad: filtro.severidad,
  });
  const data = await apiClient.get<DiscrepanciaRaw[]>(`/api/conciliacion/discrepancias/${qs}`);
  return data.map(mapperDiscrepancia);
}

export async function patchDiscrepancia(
  id: string,
  params: ResolverDiscrepanciaParams,
): Promise<DiscrepanciaEntity> {
  const data = await apiClient.patch<DiscrepanciaRaw>(
    `/api/conciliacion/discrepancias/${id}/resolver/`,
    { estado_resolucion: params.estadoResolucion, notas: params.notas },
  );
  return mapperDiscrepancia(data);
}
