import { ORQUESTADOR_API_URL } from "@/shared/commons/api";
import type {
  CheckoutSessionResult,
  GenerarCheckoutParams,
} from "../../domain/ports/repo-checkout-session";

export async function postValidarAcceso(
  params: GenerarCheckoutParams,
): Promise<CheckoutSessionResult> {
  let res: Response;
  try {
    res = await fetch(`${ORQUESTADOR_API_URL}/api/autorizacion/validar-acceso/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
      cache: "no-store",
    });
  } catch {
    return { status: "error" };
  }

  if (res.status === 403) {
    const body = await res.json().catch(() => null);
    return { status: "rechazado", motivo: body?.motivo ?? "motivo_desconocido" };
  }

  if (!res.ok) {
    return { status: "error" };
  }

  const body = await res.json().catch(() => null);
  if (!body?.checkout_token) {
    return { status: "error" };
  }

  return { status: "ok", checkoutToken: body.checkout_token };
}
