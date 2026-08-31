export const ERROR = {
  REQUIRED: "Este campo es requerido",
  MIN_LENGTH: (min: number) => `Mínimo ${min} caracteres`,
  MAX_LENGTH: (max: number) => `Máximo ${max} caracteres`,
  SELECT_OPTION: "Seleccione una opción válida",
} as const;
