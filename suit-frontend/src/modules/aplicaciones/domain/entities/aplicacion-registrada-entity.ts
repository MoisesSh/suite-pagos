export interface DominioPermitidoEntity {
  readonly id: string;
  readonly dominio: string;
  readonly activo: boolean;
}

export interface AplicacionProveedorPermitidoEntity {
  readonly id: string;
  readonly proveedor: string;
  readonly activo: boolean;
  readonly autorizadoEn: string;
}

export interface AplicacionRegistradaEntity {
  readonly id: string;
  readonly nombre: string;
  readonly appOrigenId: string;
  readonly activa: boolean;
  readonly createdAt: string;
  readonly dominios: DominioPermitidoEntity[];
  readonly proveedoresAutorizados: AplicacionProveedorPermitidoEntity[];
}

/** Shape de la respuesta de creacion (201) — mas angosta que el detalle del listado. */
export interface AplicacionCreadaEntity {
  readonly id: string;
  readonly nombre: string;
  readonly dominio: string;
  readonly proveedor: string;
}
