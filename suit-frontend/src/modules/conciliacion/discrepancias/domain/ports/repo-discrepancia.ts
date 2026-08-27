import type { DiscrepanciaEntity, EstadoResolucion } from "../entities/discrepancia-entity";

export interface DiscrepanciasFiltro {
  estadoResolucion?: EstadoResolucion;
  severidad?: string;
}

export interface ResolverDiscrepanciaParams {
  estadoResolucion: "resuelta" | "descartada" | "en_revision";
  notas: string;
}

export interface RepoDiscrepancia {
  getAll(filtro: DiscrepanciasFiltro): Promise<DiscrepanciaEntity[]>;
  resolver(id: string, params: ResolverDiscrepanciaParams): Promise<DiscrepanciaEntity>;
}
