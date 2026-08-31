"use server";

import { NoAutorizadoError, requireStaff } from "@/shared/infrastructure/auth/require-staff";
import { repoAplicacionApi } from "../repositories/repo-aplicacion-api";
import { listAplicaciones } from "../../application/use-cases/list-aplicaciones";
import { createAplicacion } from "../../application/use-cases/create-aplicacion";
import { activarAplicacion } from "../../application/use-cases/activar-aplicacion";
import { AplicacionApiError } from "../http/aplicaciones-api";
import { aplicacionFormSchema } from "../../ui/schema/schema-aplicacion";
import type { AplicacionItemDTO } from "../../application/dtos/aplicacion-dto";

export async function fetchAplicacionesAction(): Promise<AplicacionItemDTO[]> {
  await requireStaff();
  return listAplicaciones(repoAplicacionApi);
}

export async function createAplicacionAction(rawData: unknown) {
  try {
    await requireStaff();
  } catch (error) {
    if (error instanceof NoAutorizadoError) return { error: "No autorizado." };
    throw error;
  }

  const validation = aplicacionFormSchema.safeParse(rawData);
  if (!validation.success) {
    return { error: "Datos invalidos. Revisa los campos del formulario." };
  }

  try {
    await createAplicacion(repoAplicacionApi, validation.data);
    return { success: "Aplicacion registrada en suit-orquestador." };
  } catch (error) {
    if (error instanceof AplicacionApiError) return { error: error.friendlyMessage() };
    return { error: "No se pudo registrar la aplicacion. Intenta de nuevo mas tarde." };
  }
}

export async function activarAplicacionAction(id: string, activa: boolean) {
  try {
    await requireStaff();
  } catch (error) {
    if (error instanceof NoAutorizadoError) return { error: "No autorizado." };
    throw error;
  }

  try {
    await activarAplicacion(repoAplicacionApi, id, activa);
    return { success: activa ? "Aplicacion activada." : "Aplicacion desactivada." };
  } catch (error) {
    if (error instanceof AplicacionApiError) return { error: error.friendlyMessage() };
    return { error: "No se pudo cambiar el estado de la aplicacion." };
  }
}
