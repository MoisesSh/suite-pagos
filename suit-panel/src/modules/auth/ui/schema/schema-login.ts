import { z } from "zod";

export const loginFormSchema = z.object({
  email: z.string().min(1, "El email es requerido").email("Email invalido"),
  password: z.string().min(1, "La contrasena es requerida"),
});

export type LoginFormType = z.infer<typeof loginFormSchema>;
