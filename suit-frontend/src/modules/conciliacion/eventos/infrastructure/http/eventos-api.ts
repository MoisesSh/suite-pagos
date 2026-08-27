import { apiClient } from "@/shared/infrastructure/http/fetcher-api";
import { queryParams } from "@/shared/infrastructure/http/query-params";
import type { EventoEntity } from "../../domain/entities/evento-entity";
import { mapperEvento, type EventoRaw } from "../mappers/mapper-evento";

export async function getEventos(search?: string): Promise<EventoEntity[]> {
  const qs = queryParams({ search });
  const data = await apiClient.get<EventoRaw[]>(`/api/conciliacion/eventos/${qs}`);
  return data.map(mapperEvento);
}
