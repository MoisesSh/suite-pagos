import type { EstadoResolucion } from "../../domain/entities/discrepancia-entity";
import type { UsuarioResumen } from "@/shared/types/usuario";

export interface DiscrepanciaItemDTO {
  id: string;
  movimiento: string | null;
  consulta: string | null;
  evento: string | null;
  tipo: string;
  severidad: string;
  estadoResolucion: EstadoResolucion;
  resueltoPor: UsuarioResumen | null;
  resueltoAt: string | null;
  notas: string;
  createdAt: string;
}

export interface ResolverDiscrepanciaDTO {
  estadoResolucion: "resuelta" | "descartada" | "en_revision";
  notas: string;
}
