import type { AplicacionRegistradaEntity } from "../entities/aplicacion-registrada-entity";

/**
 * Puerto del dominio. La implementación real (infrastructure/repositories/)
 * todavia no existe: el CRUD de AplicacionRegistrada/DominioPermitido no está
 * expuesto por suit-orquestador (ver CONTRATO-API-ACTUAL.md, gap #1). Por eso
 * la única implementación disponible hoy es un mock (ver infrastructure/actions).
 */
export interface RepoAplicacion {
  create(params: CreateAplicacionParams): Promise<AplicacionRegistradaEntity>;
}

export interface CreateAplicacionParams {
  nombre: string;
  dominio: string;
  proveedor: string;
}
