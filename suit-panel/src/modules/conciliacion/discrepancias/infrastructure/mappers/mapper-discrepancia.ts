import type { DiscrepanciaEntity, EstadoResolucion } from "../../domain/entities/discrepancia-entity";
import type { UsuarioResumen } from "@/shared/types/usuario";

interface UsuarioResumenRaw {
  id: string;
  email: string;
  username: string;
  is_staff: boolean;
  is_superuser: boolean;
}

export interface DiscrepanciaRaw {
  id: string;
  movimiento: string | null;
  consulta: string | null;
  evento: string | null;
  tipo: string;
  severidad: string;
  estado_resolucion: EstadoResolucion;
  resuelto_por: UsuarioResumenRaw | null;
  resuelto_at: string | null;
  notas: string;
  created_at: string;
  transaccion_ledger_id: string | null;
}

function mapUsuarioResumen(raw: UsuarioResumenRaw): UsuarioResumen {
  return {
    id: raw.id,
    email: raw.email,
    username: raw.username,
    isStaff: raw.is_staff,
    isSuperuser: raw.is_superuser,
  };
}

export function mapperDiscrepancia(raw: DiscrepanciaRaw): DiscrepanciaEntity {
  return {
    id: raw.id,
    movimiento: raw.movimiento,
    consulta: raw.consulta,
    evento: raw.evento,
    tipo: raw.tipo,
    severidad: raw.severidad,
    estadoResolucion: raw.estado_resolucion,
    resueltoPor: raw.resuelto_por ? mapUsuarioResumen(raw.resuelto_por) : null,
    resueltoAt: raw.resuelto_at,
    notas: raw.notas,
    createdAt: raw.created_at,
    transaccionLedgerId: raw.transaccion_ledger_id,
  };
}
