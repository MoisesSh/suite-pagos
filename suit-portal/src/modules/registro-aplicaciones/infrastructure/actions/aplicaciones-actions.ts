"use server";

import { createAplicacion } from "../../application/use-cases/create-aplicacion";
import { repoAplicacionApi } from "../repositories/repo-aplicacion-api";
import { AplicacionApiError } from "../http/aplicaciones-api";
import { aplicacionFormSchema } from "../../ui/schema/schema-aplicacion";

export async function createAplicacionAction(rawData: unknown) {
  const validation = aplicacionFormSchema.safeParse(rawData);

  if (!validation.success) {
    return { error: "Datos inválidos. Revisa los campos del formulario." };
  }

  try {
    await createAplicacion(repoAplicacionApi, validation.data);
    return {
      success:
        "Aplicación registrada en suit-orquestador. Un administrador debe confirmar el dominio y el proveedor autorizados.",
    };
  } catch (error) {
    if (error instanceof AplicacionApiError) {
      return { error: error.friendlyMessage() };
    }
    return { error: "No se pudo registrar la aplicación. Intenta de nuevo más tarde." };
  }
}
