---
name: testing-unit-vitest
description: Tests unitarios y de componentes con Vitest + React Testing Library + MSW. Qué se puede testear y qué no en Next.js 16, convención de ubicación, y plantillas para casos de uso, schemas Zod, componentes y el cliente HTTP.
---

# Skill de tests unitarios (Vitest + RTL + MSW)

Esta skill complementa `testing-e2e-playwright`. Playwright cubre flujos completos con backend
real; esta skill cubre lógica aislada — rápida, sin red, sin navegador real.

---

## 1. Qué SÍ y qué NO testear aquí

La documentación de Next.js empaquetada en este repo
(`node_modules/next/dist/docs/01-app/02-guides/testing/vitest.md`) advierte que **Vitest no
soporta Server Components async**. En este proyecto eso se traduce en:

| Capa                                                        | ¿Vitest?     | Por qué                                                                                                                         |
| ----------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `application/use-cases/*.ts`                                | ✅           | Funciones puras, reciben el repo por parámetro (inyección)                                                                      |
| `ui/schema/schema-*.ts` (Zod)                               | ✅           | Validación pura, sin red ni DOM                                                                                                 |
| Componentes `"use client"` presentacionales                 | ✅ (RTL)     | Renderizado + props, sin Server Actions                                                                                         |
| `shared/infrastructure/http/fetcher-api.ts`                 | ✅ (con MSW) | Es la única pieza de red que vale la pena aislar — ver §4                                                                       |
| **Server Actions** (`infrastructure/actions/*.ts`)          | ❌           | Usan `cookies()` de `next/headers`, solo válido dentro del scope de request de Next — truena fuera de él. Van a Playwright E2E. |
| **Server Components async** (`app/**/page.tsx` con `await`) | ❌           | No soportado por Vitest — Playwright E2E.                                                                                       |

---

## 2. Setup (ya instalado)

```bash
pnpm add -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom @testing-library/jest-dom vite-tsconfig-paths msw
```

`vitest.config.mts` usa `projects` (lo agregó también el instalador de Storybook — ver skill
`storybook-chromatic`): el proyecto `"unit"` es el que le corresponde a esta skill.

```ts
{
  extends: true,
  test: {
    name: "unit",
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
}
```

`vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

### Scripts

```json
{
  "test:unit": "vitest run --project=unit",
  "test:unit:watch": "vitest --project=unit"
}
```

**Regla:** siempre `--project=unit`. Sin el filtro, `vitest run` intenta correr también el proyecto
`"storybook"` (tests de stories en Chromium headless vía `@vitest/browser-playwright`), que es
lento y no pertenece a esta skill — ver `storybook-chromatic`.

---

## 3. Convención de ubicación

Los tests van **al lado** del archivo que prueban, no en una carpeta `__tests__/` separada:

```
modules/ejemplo/application/use-cases/create-ejemplo.ts
modules/ejemplo/application/use-cases/create-ejemplo.test.ts

shared/ui/components/field.tsx
shared/ui/components/field.test.tsx
```

**Regla:** cuando se crea un caso de uso, un schema Zod nuevo, o un componente presentacional en
`shared/ui/components/`, se DEBE agregar su `.test.ts(x)` en el mismo commit.

---

## 4. Plantillas

### Caso de uso puro — repo fake inyectado

```ts
// modules/[modulo]/application/use-cases/[accion]-[nombre].test.ts
import { describe, expect, it, vi } from "vitest";

import type { Repo[Nombre] } from "../../domain/ports/repo-[nombre]";
import { [accion][Nombre] } from "./[accion]-[nombre]";

function fakeRepo(overrides: Partial<Repo[Nombre]> = {}): Repo[Nombre] {
  return { getAll: vi.fn(), getById: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), ...overrides };
}

describe("[accion][Nombre]", () => {
  it("delega en repo.[metodo] con los datos recibidos", async () => {
    const repo = fakeRepo({ create: vi.fn().mockResolvedValue({ id: "1" }) });
    const result = await [accion][Nombre](repo, { /* datos */ });
    expect(repo.create).toHaveBeenCalledWith({ /* datos */ });
    expect(result).toEqual({ id: "1" });
  });
});
```

Ver ejemplo real (con otro nombre de módulo): `modules/[modulo]/application/use-cases/create-[nombre].test.ts`.

### Schema Zod — casos válidos e inválidos, no solo "required"

```ts
import { describe, expect, it } from "vitest";
import { [nombre]FormSchema } from "./schema-[nombre]";

describe("[nombre]FormSchema", () => {
  it("acepta datos válidos", () => {
    expect([nombre]FormSchema.safeParse({ /* válido */ }).success).toBe(true);
  });

  it("rechaza un [campo] con formato inválido", () => {
    expect([nombre]FormSchema.safeParse({ /* inválido */ }).success).toBe(false);
  });
});
```

Prioriza casos de negocio reales sobre el regex en sí (formato de documento de identidad/teléfono
según el país de destino, uniones condicionales como `datos_tipo_a`/`datos_tipo_b` según un campo
discriminante). Ver ejemplo real (con otro nombre de módulo):
`modules/[modulo]/ui/schema/schema-[nombre].test.ts`.

### Componente presentacional — React Testing Library

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { [Componente] } from "./[componente]";

describe("[Componente]", () => {
  it("no muestra X cuando la prop no se pasa", () => {
    render(<[Componente] />);
    expect(screen.queryByText("X")).not.toBeInTheDocument();
  });

  it("muestra X cuando la prop se pasa", () => {
    render(<[Componente] prop="X" />);
    expect(screen.getByText("X")).toBeInTheDocument();
  });
});
```

Ver ejemplo real: `shared/ui/components/field.test.tsx`.

### Cliente HTTP con MSW — el test que de verdad vale la pena

Todas las llamadas HTTP del repo pasan por `shared/infrastructure/http/fetcher-api.ts`, que usa
`cookies()` de `next/headers` — hay que mockearlo, junto con `@/auth` (porque
`shared/infrastructure/http/errors.ts` importa `signOut` para `handleSessionExpired`, y eso arrastra
`next-auth` → `next/server`, que no resuelve fuera del runtime de Next):

```ts
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const cookieStore = new Map<string, { value: string }>();
const fakeCookieStore = {
  get: (name: string) => cookieStore.get(name),
  set: (name: string, value: string) => cookieStore.set(name, { value }),
  delete: (name: string) => cookieStore.delete(name),
};

vi.mock("next/headers", () => ({ cookies: async () => fakeCookieStore }));
vi.mock("@/auth", () => ({ signOut: vi.fn() }));

// Importado después de los vi.mock, y BASE_URL leído de la config real (no fijado a mano: puede
// resolver a http://backend:8000 en vez de localhost según el .env cargado).
const { apiClient } = await import("./fetcher-api");
const { API } = await import("@/shared/commons/api");
const BASE_URL = API.url;

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => cookieStore.clear());
```

Ver el archivo completo (401→refresh→retry, 403, 409, 204) en
`shared/infrastructure/http/fetcher-api.test.ts` — es la plantilla a copiar para cualquier otro
cliente HTTP que se aísle de esta forma.

---

## 5. Pre-flight checks

- [ ] ¿El test está al lado del archivo que prueba, no en `__tests__/`?
- [ ] ¿Corre con `pnpm test:unit` (proyecto `unit`, no `storybook`)?
- [ ] Si el archivo importa (directa o transitivamente) `next/headers` o `@/auth`, ¿están
      mockeados con `vi.mock`?
- [ ] Si el test necesita la URL base de la API, ¿se leyó de `@/shared/commons/api` en vez de
      fijarla a mano? (`.env` puede resolver a un host distinto de `localhost`).
- [ ] ¿`pnpm test:unit` pasa? ¿`pnpm typecheck` sigue en verde?
