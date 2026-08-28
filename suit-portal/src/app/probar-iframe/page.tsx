import { generarCheckoutDePrueba } from "@/modules/prueba-iframe/application/use-cases/generar-checkout-session";
import { repoCheckoutSessionApi } from "@/modules/prueba-iframe/infrastructure/repositories/repo-checkout-session-api";
import PruebaIframePage from "@/modules/prueba-iframe/ui/prueba-iframe-page";

// El checkout_token vence a los 15 min (CHECKOUT_TOKEN_MAX_AGE_SEGUNDOS=900 en
// suit-orquestador) — nunca debe servirse un token cacheado desde una carga
// anterior de esta ruta.
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Probar iframe de pago — Developer Portal",
};

export default async function Page() {
  const resultado = await generarCheckoutDePrueba(repoCheckoutSessionApi);
  return <PruebaIframePage resultado={resultado} />;
}
