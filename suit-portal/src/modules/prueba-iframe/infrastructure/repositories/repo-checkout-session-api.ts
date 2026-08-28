import type { RepoCheckoutSession } from "../../domain/ports/repo-checkout-session";
import { postValidarAcceso } from "../http/checkout-session-api";

export const repoCheckoutSessionApi: RepoCheckoutSession = {
  generar: postValidarAcceso,
};
