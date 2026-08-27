import { ORQUESTADOR_API_URL } from "@/shared/commons/api";
import {
  createAplicacionRegistradaEntity,
  type AplicacionRegistradaEntity,
} from "../../domain/entities/aplicacion-registrada-entity";
import type { CreateAplicacionParams } from "../../domain/ports/repo-aplicacion";

/**
 * Extrae un mensaje legible de un body de error de Django REST Framework.
 * Formas posibles: `{"dominio": ["ya existe"]}`, `{"detail": "Invalid token."}`,
 * `{"non_field_errors": ["..."]}`. Nunca asume una forma fija — DRF no la garantiza.
 */
function extractDrfMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;

  if (typeof record.detail === "string") return record.detail;

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
    super(`suit-orquestador respondió ${status} al registrar la aplicación`);
    this.name = "AplicacionApiError";
  }

  friendlyMessage(): string {
    if (this.status === 401 || this.status === 403) {
      return "El Developer Portal no está autorizado a registrar aplicaciones (token de administración inválido o ausente).";
    }
    return extractDrfMessage(this.detail) ?? "No se pudo registrar la aplicación. Verifica los datos ingresados.";
  }
}

export async function postAplicacion(
  params: CreateAplicacionParams,
): Promise<AplicacionRegistradaEntity> {
  const token = process.env.ORQUESTADOR_ADMIN_TOKEN;
  if (!token) {
    throw new Error(
      "ORQUESTADOR_ADMIN_TOKEN no está configurado — ver .env.example (sección suit-orquestador).",
    );
  }

  const res = await fetch(`${ORQUESTADOR_API_URL}/api/autorizacion/admin/aplicaciones/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Token ${token}`,
    },
    body: JSON.stringify(params),
    cache: "no-store",
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new AplicacionApiError(res.status, detail);
  }

  const data = await res.json();
  return createAplicacionRegistradaEntity({
    id: data.id,
    nombre: data.nombre,
    dominio: data.dominio,
    proveedor: data.proveedor,
  });
}
