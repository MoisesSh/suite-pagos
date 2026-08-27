"use server";

import { handleSessionExpired } from "@/shared/infrastructure/http/errors";
import { repoEventoApi } from "../repositories/repo-evento-api";
import { listEventos } from "../../application/use-cases/list-eventos";
import type { EventoItemDTO } from "../../application/dtos/evento-dto";

export async function fetchEventosAction(search?: string): Promise<EventoItemDTO[]> {
  try {
    return await listEventos(repoEventoApi, search);
  } catch (error) {
    handleSessionExpired(error);
    throw error;
  }
}
