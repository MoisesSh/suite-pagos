import type {
  AplicacionCreadaEntity,
  AplicacionRegistradaEntity,
} from "../entities/aplicacion-registrada-entity";

export interface CreateAplicacionParams {
  nombre: string;
  dominio: string;
  proveedor: string;
}

export interface RepoAplicacion {
  getAll(): Promise<AplicacionRegistradaEntity[]>;
  create(params: CreateAplicacionParams): Promise<AplicacionCreadaEntity>;
  activarDesactivar(id: string, activa: boolean): Promise<void>;
}
