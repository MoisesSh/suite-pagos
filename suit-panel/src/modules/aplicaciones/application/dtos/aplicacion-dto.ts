export interface DominioPermitidoItemDTO {
  id: string;
  dominio: string;
  activo: boolean;
}

export interface ProveedorAutorizadoItemDTO {
  id: string;
  proveedor: string;
  activo: boolean;
  autorizadoEn: string;
}

export interface AplicacionItemDTO {
  id: string;
  nombre: string;
  appOrigenId: string;
  activa: boolean;
  createdAt: string;
  dominios: DominioPermitidoItemDTO[];
  proveedoresAutorizados: ProveedorAutorizadoItemDTO[];
}

export interface CreateAplicacionDTO {
  nombre: string;
  dominio: string;
  proveedor: string;
}

export interface AplicacionCreadaDTO {
  id: string;
  nombre: string;
  dominio: string;
  proveedor: string;
}
