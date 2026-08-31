/** Extrae el valor de una cookie puntual de las cabeceras `Set-Cookie` de una respuesta `fetch`. */
export function extractSetCookieValue(res: Response, cookieName: string): string | null {
  const setCookieHeaders =
    typeof res.headers.getSetCookie === "function"
      ? res.headers.getSetCookie()
      : [res.headers.get("set-cookie") ?? ""];

  for (const header of setCookieHeaders) {
    const match = header.match(new RegExp(`(?:^|;\\s*)${cookieName}=([^;]+)`));
    if (match) return decodeURIComponent(match[1]);
  }
  return null;
}
