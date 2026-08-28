import type {
  GenerarCheckoutParams,
  RepoCheckoutSession,
} from "../../domain/ports/repo-checkout-session";

// Datos de prueba fijos: la app real declararía su propio monto/moneda/concepto
// al iniciar el checkout; esta pantalla es un banco de pruebas del Portal, no
// un checkout real, así que el valor viaja hardcodeado a propósito.
const CHECKOUT_DE_PRUEBA: GenerarCheckoutParams = {
  dominio: "localhost",
  proveedor: "BDV",
  monto: "1000.60",
  moneda: "VES",
  concepto: "Prueba desde Developer Portal",
};

export async function generarCheckoutDePrueba(repo: RepoCheckoutSession) {
  return repo.generar(CHECKOUT_DE_PRUEBA);
}
