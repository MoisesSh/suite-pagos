import type { UsuarioResumen } from "@/shared/types/usuario";

export type EstadoResolucion = "abierta" | "resuelta" | "descartada" | "en_revision";

export interface DiscrepanciaEntity {
  readonly id: string;
  readonly movimiento: string | null;
  readonly consulta: string | null;
  readonly evento: string | null;
  readonly tipo: string;
  readonly severidad: string;
  readonly estadoResolucion: EstadoResolucion;
  readonly resueltoPor: UsuarioResumen | null;
  readonly resueltoAt: string | null;
  readonly notas: string;
  readonly createdAt: string;
}
