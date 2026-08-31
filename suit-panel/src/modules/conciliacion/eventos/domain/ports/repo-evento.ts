import type { EventoEntity } from "../entities/evento-entity";

export interface RepoEvento {
  getAll(search?: string): Promise<EventoEntity[]>;
}
