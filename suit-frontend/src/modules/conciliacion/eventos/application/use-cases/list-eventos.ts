import type { RepoEvento } from "../../domain/ports/repo-evento";
import type { EventoItemDTO } from "../dtos/evento-dto";

export async function listEventos(repo: RepoEvento, search?: string): Promise<EventoItemDTO[]> {
  const entities = await repo.getAll(search);
  return entities.map((entity) => ({
    id: entity.id,
    eventId: entity.eventId,
    eventType: entity.eventType,
    schemaVersion: entity.schemaVersion,
    procesadoAt: entity.procesadoAt,
    createdAt: entity.createdAt,
  }));
}
