import { z } from "zod";
import { APP_NAME, APP_NAME_MSG, DOMAIN, DOMAIN_MSG } from "@/shared/validation/regex";
import { ERROR } from "@/shared/validation/messages";

// Único proveedor real confirmado hasta ahora (db-plan-pagos.md §2.5, suit-orquestador):
// BDV Pago Móvil C2P. Catálogo cerrado — no texto libre — para no anticipar
// proveedores que el backend todavia no soporta.
export const PROVEEDOR_OPTIONS = ["BDV"] as const;

export const aplicacionFormSchema = z.object({
  nombre: z
    .string()
    .min(2, ERROR.MIN_LENGTH(2))
    .max(100, ERROR.MAX_LENGTH(100))
    .regex(APP_NAME, APP_NAME_MSG),
  dominio: z
    .string()
    .min(4, ERROR.MIN_LENGTH(4))
    .max(253, ERROR.MAX_LENGTH(253))
    .regex(DOMAIN, DOMAIN_MSG),
  proveedor: z.enum(PROVEEDOR_OPTIONS, {
    error: ERROR.SELECT_OPTION,
  }),
});

export type AplicacionFormType = z.infer<typeof aplicacionFormSchema>;
