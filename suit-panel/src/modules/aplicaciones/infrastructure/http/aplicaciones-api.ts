import { API } from "@/shared/commons/api";
import type { AplicacionCreadaEntity, AplicacionRegistradaEntity } from "../../domain/entities/aplicacion-registrada-entity";
import type { CreateAplicacionParams } from "../../domain/ports/repo-aplicacion";
import { mapperAplicacion, type AplicacionRegistradaRaw } from "../mappers/mapper-aplicacion";

const ERROR_CODE_MESSAGES: Record<string, string> = {
  proveedor_no_encontrado: "El proveedor de pago no existe en el catálogo.",
  dominio_ya_registrado: "El dominio ya está registrado en otra aplicación.",
};

/**
 * Extrae un mensaje legible de un body de error de Django REST Framework.
 * Formas posibles: `{"error": "dominio_ya_registrado"}`, `{"dominio": ["ya existe"]}`,
 * `{"detail": "Invalid token."}`, `{"non_field_errors": ["..."]}`. Nunca asume una
 * forma fija — DRF no la garantiza.
 */
function extractDrfMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;

  if (typeof record.detail === "string") return record.detail;
  if (typeof record.error === "string") return ERROR_CODE_MESSAGES[record.error] ?? record.error;

  for (const key of ["non_field_errors", "dominio", "nombre", "proveedor"]) {
    const value = record[key];
    if (Array.isArray(value) && typeof value[0] === "string") {
      return key === "non_field_errors" ? value[0] : `${key}: ${value[0]}`;
    }
  }

  return null;
}

export class AplicacionApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(`suit-orquestador respondio ${status}`);
    this.name = "AplicacionApiError";
  }

  friendlyMessage(): string {
    if (this.status === 401 || this.status === 403) {
      return "suit-panel no esta autorizado a administrar aplicaciones (token de servicio invalido o ausente).";
    }
    return extractDrfMessage(this.detail) ?? "No se pudo completar la operacion. Verifica los datos ingresados.";
  }
}

function authHeaders(): Record<string, string> {
  const token = process.env.ORQUESTADOR_ADMIN_TOKEN;
  if (!token) {
    throw new Error("ORQUESTADOR_ADMIN_TOKEN no esta configurado — ver .env.example.");
  }
  return { Authorization: `Token ${token}` };
}

export async function getAplicaciones(): Promise<AplicacionRegistradaEntity[]> {
  const res = await fetch(`${API.orquestadorUrl}/api/autorizacion/admin/aplicaciones/`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw new AplicacionApiError(res.status, await res.json().catch(() => null));

  const data = (await res.json()) as AplicacionRegistradaRaw[];
  return data.map(mapperAplicacion);
}

export async function postAplicacion(params: CreateAplicacionParams): Promise<AplicacionCreadaEntity> {
  const res = await fetch(`${API.orquestadorUrl}/api/autorizacion/admin/aplicaciones/`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(params),
    cache: "no-store",
  });
  if (!res.ok) throw new AplicacionApiError(res.status, await res.json().catch(() => null));

  const data = await res.json();
  return { id: data.id, nombre: data.nombre, dominio: data.dominio, proveedor: data.proveedor };
}

export async function patchAplicacionActiva(id: string, activa: boolean): Promise<void> {
  const res = await fetch(`${API.orquestadorUrl}/api/autorizacion/admin/aplicaciones/${id}/`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ activa }),
    cache: "no-store",
  });
  if (!res.ok) throw new AplicacionApiError(res.status, await res.json().catch(() => null));
}
