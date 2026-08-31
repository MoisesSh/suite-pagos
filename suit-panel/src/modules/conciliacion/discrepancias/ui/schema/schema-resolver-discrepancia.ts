import { z } from "zod";

export const resolverDiscrepanciaFormSchema = z.object({
  estadoResolucion: z.enum(["resuelta", "descartada", "en_revision"], {
    message: "Seleccione un estado",
  }),
  notas: z.string(),
});

export type ResolverDiscrepanciaFormType = z.infer<typeof resolverDiscrepanciaFormSchema>;
