import type { AplicacionRegistradaEntity } from "../../domain/entities/aplicacion-registrada-entity";

export interface DominioPermitidoRaw {
  id: string;
  dominio: string;
  activo: boolean;
}

export interface ProveedorAutorizadoRaw {
  id: string;
  proveedor: string;
  activo: boolean;
  autorizado_en: string;
}

export interface AplicacionRegistradaRaw {
  id: string;
  nombre: string;
  app_origen_id: string;
  activa: boolean;
  created_at: string;
  dominios: DominioPermitidoRaw[];
  proveedores_autorizados: ProveedorAutorizadoRaw[];
}

export function mapperAplicacion(raw: AplicacionRegistradaRaw): AplicacionRegistradaEntity {
  return {
    id: raw.id,
    nombre: raw.nombre,
    appOrigenId: raw.app_origen_id,
    activa: raw.activa,
    createdAt: raw.created_at,
    dominios: raw.dominios.map((d) => ({ id: d.id, dominio: d.dominio, activo: d.activo })),
    proveedoresAutorizados: raw.proveedores_autorizados.map((p) => ({
      id: p.id,
      proveedor: p.proveedor,
      activo: p.activo,
      autorizadoEn: p.autorizado_en,
    })),
  };
}
