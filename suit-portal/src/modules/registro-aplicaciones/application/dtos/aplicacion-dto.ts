export interface AplicacionItemDTO {
  id: string;
  nombre: string;
  dominio: string;
  proveedor: string;
}

export interface CreateAplicacionDTO {
  nombre: string;
  dominio: string;
  proveedor: string;
}
