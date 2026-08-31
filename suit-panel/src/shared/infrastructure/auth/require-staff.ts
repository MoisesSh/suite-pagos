import { auth } from "@/auth";

export class NoAutorizadoError extends Error {
  override readonly name = "NoAutorizadoError";
}

/**
 * suit-orquestador confia ciegamente en ORQUESTADOR_ADMIN_TOKEN (token estatico
 * de servicio, sin usuario real detras) — la unica barrera de "solo staff" es
 * esta verificacion de nuestra propia sesion, no el backend.
 */
export async function requireStaff(): Promise<void> {
  const session = await auth();
  if (!session?.user.isStaff) throw new NoAutorizadoError();
}
