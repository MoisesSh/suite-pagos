"use server";

import { createAplicacion } from "../../application/use-cases/create-aplicacion";
import { repoAplicacionMock } from "../repositories/repo-aplicacion-mock";
import { aplicacionFormSchema } from "../../ui/schema/schema-aplicacion";

/**
 * MOCKEADO A PROPÓSITO — sin conexión a backend real.
 *
 * TODO(gap #1 CONTRATO-API-ACTUAL.md): suit-orquestador todavia no expone
 * ningún endpoint para crear AplicacionRegistrada/DominioPermitido/
 * AplicacionProveedorPermitido — solo se gestiona por Django admin hoy. Cuando
 * ese CRUD exista, reemplazar `repoAplicacionMock` por un repo real
 * (infrastructure/repositories/repo-aplicacion-api.ts) que llame al endpoint
 * de suit-orquestador, sin tocar application/ ni ui/.
 */
export async function createAplicacionAction(rawData: unknown) {
  const validation = aplicacionFormSchema.safeParse(rawData);

  if (!validation.success) {
    return { error: "Datos inválidos. Revisa los campos del formulario." };
  }

  try {
    await createAplicacion(repoAplicacionMock, validation.data);
    return {
      success:
        "Solicitud registrada (simulada). Todavía no se envía a ningún backend real — ver nota en pantalla.",
    };
  } catch {
    return { error: "Error al registrar la aplicación (simulado)" };
  }
}
