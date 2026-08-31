---
name: validacion-input-protegido
description: Protección de entradas de datos con regex globales reutilizables. Crea variables exportables globales para validar documento de identidad, email, teléfono, nombres, direcciones, contraseñas, fechas, números y más. Funciona con Zod, Yup, Joi o cualquier schema validator. Los regex de identificación (cédula/RIF/teléfono/placa) se muestran con formato venezolano como ejemplo concreto — reemplazar por el formato del país/mercado objetivo del proyecto.
---

# Skill de Validación de Entradas

Esta skill complementa la arquitectura Scream-Feature-Onion. Cada schema Zod en `ui/schema/` DEBE usar regex globales compartidos. Ningún campo string debe quedar sin validación de formato.

---

## 0. REGLA FUNDAMENTAL: NO AL HARDCODEO

### ❌ NO hardcodear en la UI ni en schemas:

- **Regex** en schemas Zod o server actions → importar de `shared/validation/regex.ts`
- **Mensajes de error** inline en strings → importar de `shared/validation/messages.ts`
- **URLs, endpoints, tokens** en componentes → usar `shared/commons/api.ts` + `.env`
- **Colores, medidas, z-index, radios** en el JSX → usar variables CSS de `globals.css`
- **Nombres de campos, opciones de selects repetidos** → exportar como `as const` desde un archivo compartido
- **Strings visibles al usuario** (títulos, descripciones, placeholders) → constante exportada o `messages.ts`

### ✅ Única excepción: estatus del backend

Los **estatus** (`estatus` de Usuario, Pedido, Solicitud, Verificacion) pueden hardcodearse en componentes de UI porque son valores definidos por el backend, se usan en condicionales de rendering en tiempo real y varían según el contexto:

```typescript
// ✅ Permitido: hardcodeo de estatus en badges de UI
const STATUS_CONFIG = {
  creado: { label: "Creado", color: "blue" },
  perfil_completo: { label: "Perfil Completo", color: "gold" },
  registro_completo: { label: "Registro Completo", color: "gold" },
  pendiente_verificacion: { label: "Pendiente", color: "gold" },
  verificado: { label: "Verificado", color: "green" },
  rechazado: { label: "Rechazado", color: "red" },
  observado: { label: "Observado", color: "gold" },
} as const;
```

También se permite hardcodear estatus de:

- **Pedidos:** `pendiente`, `aprobado`, `rechazado`, `activo`
- **Solicitudes:** `pendiente`, `aceptado`, `rechazado`
- **Verificacion:** `pendiente`, `ok`, `rechazado`

### ✅ Hardcodear SOLO si:

- Es un literal puro que nunca cambiará (ej: `z.literal("operador")`, `as const`)
- Es configuración del framework (ej: `revalidatePath("/ruta")`)
- Es un mock / demo / placeholder temporal — con un `// TODO:` comment

### 👮 Regla de revisión

Si un mismo valor aparece **dos veces** en el código ya está mal. Centralizar en el primer archivo que lo necesite. La excepción de estatus no aplica a otras strings.

---

## 1. Archivo de regex globales

### Ubicación

```
shared/validation/regex.ts       # Constantes regex exportadas
shared/validation/messages.ts    # Mensajes de error reutilizables
shared/validation/index.ts       # Barrel export
```

### Template completo

```typescript
// shared/validation/regex.ts
// ===========================
// REGEX GLOBALES REUTILIZABLES
// ===========================
// Cada regex tiene su mensaje de error asociado.
// Usar en schemas Zod (ui/schema/) y en server actions (infrastructure/actions/).

// --- Identificación regional (ejemplo: Venezuela — reemplazar por el formato del país/mercado objetivo) ---

/** Cédula de identidad: V/E/J/P/G + 6 a 9 dígitos */
export const CEDULA = /^[VEJPG]\d{6,9}$/;
export const CEDULA_MSG = "Debe ser una letra (V/E/J/P/G) seguida de 6 a 9 dígitos";

/** RIF: letra (J/G/V/E) + guión + 8 dígitos + guión + 1 dígito verificador */
export const RIF = /^[JPGVE]-\d{8}-\d$/;
export const RIF_MSG = "Formato inválido. Ejemplo: J-12345678-9";

/** Teléfono Venezuela: 0412-1234567 o +58412-1234567 */
export const PHONE_VE = /^(\+58)?4\d{2}-\d{7}$/;
export const PHONE_VE_MSG = "Formato: 0412-1234567 o +58412-1234567";

/** Código postal Venezuela: 4 dígitos */
export const ZIP_VE = /^\d{4}$/;
export const ZIP_VE_MSG = "Código postal: 4 dígitos";

// --- Contacto ---

/** Email estándar */
export const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const EMAIL_MSG = "Correo electrónico inválido";

/** Teléfono internacional: +pais código (ej: +584121234567) */
export const PHONE_INTL = /^\+\d{7,15}$/;
export const PHONE_INTL_MSG = "Formato: +584121234567";

// --- Texto general ---

/** Nombres: letras (incluyendo acentos y ñ), espacios, hasta 100 caracteres */
export const NAME = /^[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]{2,100}$/;
export const NAME_MSG = "Solo letras y espacios (2 a 100 caracteres)";

/** Apellidos: igual que NAME */
export const SURNAME = NAME;
export const SURNAME_MSG = "Solo letras y espacios (2 a 100 caracteres)";

/** Direcciones: letras, números, espacios, guiones, puntos, comas, # */
export const ADDRESS = /^[a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s\-,.#/ºª]{5,200}$/;
export const ADDRESS_MSG = "Dirección inválida (5 a 200 caracteres)";

/** Texto seguro (descripciones, observaciones): sin HTML ni caracteres de control */
export const SAFE_TEXT = /^[a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s\-,.#;:()/ºª!?@]+$/;
export const SAFE_TEXT_MSG = "Contiene caracteres no permitidos";

// --- Seguridad ---

/** Contraseña: mayúscula + minúscula + número + especial, mínimo 8 */
export const PASSWORD =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;
export const PASSWORD_MSG =
  "Mínimo 8 caracteres, una mayúscula, una minúscula, un número y un carácter especial";

/** Sin etiquetas HTML ni XML */
export const NO_HTML = /^[^<>&"]*$/;
export const NO_HTML_MSG = 'No se permiten caracteres HTML (< > & ")';

/** Sin caracteres de SQL injection (básico) */
export const NO_SQL = /^[^;'"]*$/;
export const NO_SQL_MSG = "No se permiten caracteres SQL (; ' \")";

// --- Numéricos ---

/** Solo dígitos (1 o más) */
export const DIGITS = /^\d+$/;
export const DIGITS_MSG = "Solo números";

/** Número entero (opcional negativo) */
export const INTEGER = /^-?\d+$/;
export const INTEGER_MSG = "Debe ser un número entero";

/** Número decimal (opcional negativo, punto decimal) */
export const DECIMAL = /^-?\d+(\.\d+)?$/;
export const DECIMAL_MSG = "Debe ser un número decimal";

// --- Códigos e identificadores ---

/** Alfanumérico con guiones y underscores */
export const ALPHANUMERIC = /^[a-zA-Z0-9_-]+$/;
export const ALPHANUMERIC_MSG = "Solo letras, números, guiones y underscores";

/** UUID v4 */
export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const UUID_MSG = "UUID inválido";

/** Hex color: #RGB, #RRGGBB, #RGBA, #RRGGBBAA */
export const HEX_COLOR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{8})$/;
export const HEX_COLOR_MSG = "Color hex inválido. Ejemplo: #FF5733";

/** URL http/https */
export const URL = /^https?:\/\/[^\s/$.?#].[^\s]*$/i;
export const URL_MSG = "URL inválida. Debe comenzar con http:// o https://";

// --- Fechas ---

/** Fecha ISO: YYYY-MM-DD */
export const DATE_ISO = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;
export const DATE_ISO_MSG = "Fecha inválida. Formato: YYYY-MM-DD";

/** Hora: HH:MM (24h) */
export const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
export const TIME_MSG = "Hora inválida. Formato: HH:MM";

/** Fecha + hora ISO: YYYY-MM-DDTHH:MM */
export const DATETIME_LOCAL =
  /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])T([01]\d|2[0-3]):[0-5]\d$/;
export const DATETIME_LOCAL_MSG = "Fecha y hora inválida. Formato: YYYY-MM-DDTHH:MM";

// --- Transporte (ejemplo: formato de placa venezolana — adaptar al país/dominio del proyecto) ---

/** Placa vehículo Venezuela: 3 letras + 3 números (formato antiguo) o 4 letras + 2 números (nuevo) */
export const PLACA_VE = /^([A-Z]{3}\d{3}|[A-Z]{4}\d{2})$/;
export const PLACA_VE_MSG = "Placa inválida. Formato: ABC123 o ABCD12";
```

### Mensajes de error

```typescript
// shared/validation/messages.ts
export const ERROR = {
  REQUIRED: "Este campo es requerido",
  MIN_LENGTH: (min: number) => `Mínimo ${min} caracteres`,
  MAX_LENGTH: (max: number) => `Máximo ${max} caracteres`,
  INVALID_EMAIL: "Correo electrónico inválido",
  INVALID_PASSWORD:
    "La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula, un número y un carácter especial",
  INVALID_CEDULA: "Cédula inválida. Debe ser V/E/J/P/G seguido de 6 a 9 dígitos",
  INVALID_RIF: "RIF inválido. Formato: J-12345678-9",
  INVALID_PHONE: "Teléfono inválido. Formato: 0412-1234567",
  INVALID_DATE: "Fecha inválida. Formato: YYYY-MM-DD",
  INVALID_NUMBER: "Debe ser un número",
  ONLY_LETTERS: "Solo se permiten letras",
  ONLY_DIGITS: "Solo se permiten números",
  NO_HTML: "No se permiten etiquetas HTML",
  PASSWORDS_DONT_MATCH: "Las contraseñas no coinciden",
} as const;
```

### Barrel export

```typescript
// shared/validation/index.ts
export * from "./regex";
export * from "./messages";
```

---

## 2. Integración con Zod

### Reglas

1. **Todo schema** en `ui/schema/schema-[nombre].ts` DEBE usar regex de `shared/validation/regex.ts` para campos string.
2. **No hardcodear regex** en los schemas. Siempre importar desde `@/shared/validation`.
3. **Los mensajes** deben ser los exportados de `regex.ts` o `messages.ts`, no strings inline.

### Schema con regex (template canónico)

```typescript
// modules/[modulo]/ui/schema/schema-[nombre].ts
import { z } from "zod";
import {
  CEDULA, CEDULA_MSG,
  EMAIL, EMAIL_MSG,
  NAME, NAME_MSG,
  PHONE_VE, PHONE_VE_MSG,
  SAFE_TEXT, SAFE_TEXT_MSG,
} from "@/shared/validation/regex";
import { ERROR } from "@/shared/validation/messages";

export const [nombre]FormSchema = z.object({
  // Campos con regex global
  cedula: z.string().regex(CEDULA, CEDULA_MSG),
  email: z.string().regex(EMAIL, EMAIL_MSG),
  nombre: z.string()
    .min(2, ERROR.MIN_LENGTH(2))
    .max(100, ERROR.MAX_LENGTH(100))
    .regex(NAME, NAME_MSG),
  telefono: z.string().regex(PHONE_VE, PHONE_VE_MSG).optional().or(z.literal("")),
  descripcion: z.string()
    .min(10, ERROR.MIN_LENGTH(10))
    .max(500, ERROR.MAX_LENGTH(500))
    .regex(SAFE_TEXT, SAFE_TEXT_MSG),
});

export type [Nombre]FormType = z.infer<typeof [nombre]FormSchema>;
```

### Schema con refine (validación compuesta)

```typescript
export const usuarioFormSchema = z
  .object({
    password: z.string().regex(PASSWORD, PASSWORD_MSG),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Las contraseñas no coinciden",
    path: ["confirmPassword"],
  });
```

### Schema con transform (sanitización)

```typescript
export const [nombre]FormSchema = z.object({
  nombre: z.string()
    .transform((s) => s.trim().replace(/\s+/g, " "))
    .pipe(z.string().min(2).max(100).regex(NAME, NAME_MSG)),
  email: z.string()
    .transform((s) => s.trim().toLowerCase())
    .pipe(z.string().regex(EMAIL, EMAIL_MSG)),
});
```

### Schema select con z.enum

```typescript
const tipoOptions = ["Opción 1", "Opción 2", "Opción 3"] as const;

export const [nombre]FormSchema = z.object({
  tipo: z.enum(tipoOptions, {
    errorMap: () => ({ message: "Seleccione una opción válida" }),
  }),
});
```

### Schema numérico con validación

```typescript
export const [nombre]FormSchema = z.object({
  edad: z.coerce.number()
    .int("Debe ser un número entero")
    .min(18, "Debe ser mayor de edad")
    .max(120, "Edad inválida"),
  monto: z.coerce.number()
    .positive("Debe ser un número positivo")
    .max(999999.99, "Monto máximo excedido"),
});
```

---

## 3. Validación en server actions con Zod

### Regla fundamental (Zero-Trust)

`schema.safeParse()` no lanza error. Devuelve `{ success: true, data }` o `{ success: false, error }`. Toda server action DEBE validar los datos de entrada contra el mismo schema del formulario. El cliente puede mentir; el servidor no confía.

### Template canónico (parámetro unknown)

```typescript
"use server";

import { [nombre]FormSchema } from "../ui/schema/schema-[nombre]";

export async function create[Nombre]Action(rawData: unknown) {
  const validation = [nombre]FormSchema.safeParse(rawData);

  if (!validation.success) {
    // validation.error.flatten().fieldErrors → { campo1: ["error"], campo2: ["error"] }
    return;
  }

  // validation.data está 100% tipado por el schema
  const { campo1, campo2 } = validation.data;
}
```

### FormData (formularios nativos)

Cuando el formulario usa `<form action={action}>`, el parámetro es `FormData`. Extraer con `Object.fromEntries()` y pasar por `safeParse`:

```typescript
export async function create[Nombre]Action(formData: FormData) {
  const raw = Object.fromEntries(formData);
  const validation = [nombre]FormSchema.safeParse(raw);

  if (!validation.success) return;

  const { campo1 } = validation.data;
}
```

### ❌ No hacer

````typescript
// ❌ Parámetro Record<string, unknown> — saltea la validación del schema
export async function action(data: Record<string, unknown>) {}

// ❌ Validación manual con regex — el schema ya tiene las reglas
export async function action(data: FormData) {
  if (!CEDULA.test(data.get("cedula"))) return;
}

// ❌ FormData sin safeParse — datos sin tipar ni validar
export async function action(formData: FormData) {
  const cedula = formData.get("cedula"); // tipo: unknown
}

---

## 4. Sanitización básica

Funciones helper para limpiar inputs antes de validar.

```typescript
// shared/validation/sanitize.ts

/** Elimina espacios al inicio y final, normaliza espacios múltiples */
export function normalizeSpaces(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

/** Convierte a minúsculas y normaliza */
export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

/** Elimina caracteres de control (no imprimibles) */
export function stripControlChars(value: string): string {
  return value.replace(/[\x00-\x1F\x7F]/g, "");
}

/** Elimina etiquetas HTML/XML */
export function stripHtml(value: string): string {
  return value.replace(/<[^>]*>/g, "");
}

/** Sanitización completa para texto seguro */
export function sanitizeText(value: string): string {
  return stripControlChars(normalizeSpaces(value));
}
````

---

## 5. Casos específicos de identificación regional (ejemplo Venezuela — adaptar al país objetivo)

### Cédula (venezolana) — casos borde

```typescript
// La cédula venezolana puede ser:
//   V-12345678  (nacional)
//   E-12345678  (extranjero)
//   J-12345678  (jurídico, aunque esto es RIF)
//   P-12345678  (pasaporte)
//   G-12345678  (gobierno)

// Regex flexible (acepta letra + dígitos sin guión)
export const CEDULA = /^[VEJPG]\d{6,9}$/;

// Para el backend, a veces se almacena sin la letra (solo dígitos)
export const CEDULA_NUMEROS = /^\d{6,9}$/;
```

### Validación de cédula con dígito verificador (si aplica)

```typescript
// Algunos sistemas usan un algoritmo de verificación (módulo 11)
export function validarCedulaConDigito(cedula: string): boolean {
  if (!CEDULA_NUMEROS.test(cedula)) return false;
  // Implementar algoritmo de verificación si el backend lo requiere
  return true;
}
```

---

## 6. Seguridad adicional

### Reglas de protección de entradas

1. **Toda entrada** que viene del usuario (formularios, query params, URL params) DEBE ser validada con regex.
2. **No confiar en el cliente.** Aunque el frontend valide con Zod, el server action DEBE re-validar con los mismos regex.
3. **Sanitizar antes de almacenar:** aplicar `normalizeSpaces()`, `stripHtml()`, `stripControlChars()`.
4. **Escapar en la salida:** Next.js escapa automáticamente, pero si se usa `dangerouslySetInnerHTML`, sanitizar con `stripHtml()`.
5. **Campos numéricos:** siempre usar `z.coerce.number()` o `parseInt()` explícito, nunca confiar en `string` para operaciones numéricas.

### Prevención de inyección

```typescript
// shared/validation/sanitize.ts

/** Detecta intentos de SQL injection básicos */
export function hasSqlInjection(value: string): boolean {
  const patterns = [
    /(\bSELECT\b.*\bFROM\b)/i,
    /(\bDROP\b.*\bTABLE\b)/i,
    /(\bDELETE\b.*\bFROM\b)/i,
    /(\bINSERT\b.*\bINTO\b)/i,
    /(\bUNION\b.*\bSELECT\b)/i,
    /('.*--)/,
    /('.*#)/,
    /(\bOR\b.*\d+\s*=\s*\d+)/i,
  ];
  return patterns.some((p) => p.test(value));
}
```

---

## 7. Pre-flight checks

Antes de dar por terminado cualquier schema o action:

- [ ] **Todo campo string** en el schema tiene al menos `.min()` + `.max()` + `.regex()`?
- [ ] **Los regex** están importados de `shared/validation/regex.ts`, no hardcodeados?
- [ ] **Los mensajes de error** son claros para el usuario final (no mensajes técnicos)?
- [ ] **La server action** re-valida los datos con regex (no confía solo en el cliente)?
- [ ] **Campos opcionales** manejan `undefined`/`""` correctamente (`.optional().or(z.literal(""))`)?
- [ ] **Campos numéricos** usan `z.coerce.number()` en vez de `z.string()`?
- [ ] **Sanitización** aplicada: trim, normalizeSpaces, stripHtml donde corresponda?
- [ ] **Regex probados** contra casos borde: string vacío, whitespace, unicode, caracteres especiales?
- [ ] **Cédula/RIF** probados con formatos válidos e inválidos (V/E/J/P/G, longitud)?
- [ ] **Contraseña** probada con y sin mayúsculas, números, especiales?
- [ ] **No hay regex falseando** validaciones incorrectas (ej: nombre aceptando números)?
- [ ] **El barrel export** de `shared/validation/index.ts` exporta todo correctamente?
- [ ] **NO HARDCODEO:** los regex, mensajes, endpoints, colores y strings de UI están en archivos compartidos, no escritos inline? (solo se hardcodean estatus del backend)

Si alguna respuesta es NO, el módulo no está completo.
