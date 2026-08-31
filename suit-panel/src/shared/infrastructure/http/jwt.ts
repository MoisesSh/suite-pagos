/** Decodifica (sin verificar firma) el claim `exp` de un JWT y lo devuelve en epoch ms. */
export function decodeJwtExpiry(token: string): number {
  const payload = token.split(".")[1];
  if (!payload) throw new Error("Token JWT invalido: falta el payload");
  const json = Buffer.from(payload, "base64url").toString("utf-8");
  const { exp } = JSON.parse(json) as { exp: number };
  return exp * 1000;
}
