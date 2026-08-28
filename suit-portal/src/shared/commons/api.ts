/** URL pública del visor de documentación OpenAPI de suit-conciliacion (único backend con Swagger hoy). */
export const CONCILIACION_DOCS_URL =
  process.env.NEXT_PUBLIC_CONCILIACION_DOCS_URL ?? "http://localhost:8000/api/docs/";

/** URL server-only de suit-orquestador (CRUD admin de aplicaciones/dominios). Nunca exponer al cliente. */
export const ORQUESTADOR_API_URL = process.env.ORQUESTADOR_API_URL ?? "http://localhost:8001";

/** URL pública de suit-orquestador, alcanzable por el navegador (src del iframe de /probar-iframe). */
export const ORQUESTADOR_PUBLIC_URL =
  process.env.NEXT_PUBLIC_ORQUESTADOR_PUBLIC_URL ?? "http://localhost:8001";
