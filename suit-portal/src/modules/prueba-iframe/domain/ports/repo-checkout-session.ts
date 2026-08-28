export interface GenerarCheckoutParams {
  dominio: string;
  proveedor: string;
  monto: string;
  moneda: string;
  concepto: string;
}

/**
 * Resultado de intentar abrir una sesión de checkout. Unión discriminada:
 * `rechazado` es un 403 de negocio del Orquestador (dominio/app/proveedor no
 * autorizado — db-plan-pagos.md 2.0), `error` es una falla de transporte/parseo
 * ajena a esa decisión de negocio. Nunca colapsar ambos en un solo booleano.
 */
export type CheckoutSessionResult =
  | { status: "ok"; checkoutToken: string }
  | { status: "rechazado"; motivo: string }
  | { status: "error" };

export interface RepoCheckoutSession {
  generar(params: GenerarCheckoutParams): Promise<CheckoutSessionResult>;
}
