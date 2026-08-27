export interface AplicacionRegistradaEntity {
  readonly id: string;
  nombre: string;
  dominio: string;
  proveedor: string;
}

export function createAplicacionRegistradaEntity(
  entity: AplicacionRegistradaEntity,
): AplicacionRegistradaEntity {
  if (!entity.nombre) throw new Error("AplicacionRegistrada: nombre requerido");
  if (!entity.dominio) throw new Error("AplicacionRegistrada: dominio requerido");
  if (!entity.proveedor) throw new Error("AplicacionRegistrada: proveedor requerido");
  return entity;
}
