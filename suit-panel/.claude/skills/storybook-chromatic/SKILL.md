---
name: storybook-chromatic
description: Storybook + Chromatic para un proyecto Next.js + React + Tailwind. Convención de stories, theming multi-tema (claro/oscuro/marca), y el flujo de regresión visual con Chromatic.
---

# Skill de Storybook + Chromatic

Storybook aísla componentes de UI fuera del árbol completo de la app, para poder verlos y probarlos
uno por uno. Chromatic toma capturas de cada story y avisa cuando el diseño cambia sin querer
(regresión visual).

---

## 1. Setup (ya instalado)

Se instaló con el inicializador oficial (`pnpm dlx storybook@latest init`), que detectó
Next.js 16 / React 19 y eligió su propio framework — no fijar versiones a mano si se reinstala
desde cero, dejar que el inicializador decida (este proyecto usa Next.js con cambios de ruptura
respecto a versiones anteriores, ver `AGENTS.md`).

- Framework: `@storybook/nextjs-vite` (Vite, no webpack — compatible de forma nativa con el
  `@tailwindcss/postcss` de Tailwind v4 que ya usa el proyecto).
- Addons: `@storybook/addon-a11y`, `@storybook/addon-docs`, `@chromatic-com/storybook`,
  `@storybook/addon-vitest`.
- `@storybook/addon-vitest` conecta las stories con Vitest: cada story se corre también como test
  automático en Chromium headless, en el proyecto `"storybook"` de `vitest.config.mts` (separado
  del proyecto `"unit"` de la skill `testing-unit-vitest` — no se ejecutan juntos con
  `pnpm test:unit`, ver esa skill para el porqué).

### Scripts

```json
{
  "storybook": "storybook dev -p 6006",
  "build-storybook": "storybook build",
  "test:storybook": "vitest run --project=storybook",
  "chromatic": "chromatic --exit-zero-on-changes"
}
```

---

## 2. Convención de ubicación

Las stories van **al lado** del componente, igual que los tests unitarios — nunca en una carpeta
`stories/` separada (esa carpeta es el boilerplate genérico del inicializador de Storybook, se
borró):

```
components/ui/button.tsx
components/ui/button.stories.tsx

modules/ejemplo/ui/kpi-cards.tsx
modules/ejemplo/ui/kpi-cards.stories.tsx
```

`.storybook/main.ts` ya apunta a los 3 árboles donde puede haber stories:

```ts
stories: [
  "../modules/**/*.stories.@(ts|tsx)",
  "../shared/**/*.stories.@(ts|tsx)",
  "../components/**/*.stories.@(ts|tsx)",
],
```

**Regla:** todo componente presentacional nuevo en `shared/ui/components/` o `components/ui/` que
tenga más de una variante visual relevante (variantes de `Button`, estados de `Field` con/sin
error, tarjetas con datos vs. vacías) DEBE tener su `.stories.tsx`.

---

## 3. Plantilla

```tsx
import type { Meta, StoryObj } from "@storybook/nextjs-vite";

import { [Componente] } from "./[componente]";

const meta = {
  title: "[Grupo]/[Componente]",
  component: [Componente],
  parameters: { layout: "padded" }, // o "centered" para componentes chicos como un botón
} satisfies Meta<typeof [Componente]>;

export default meta;

type Story = StoryObj<typeof meta>;

export const ConDatos: Story = {
  args: { /* props reales, no lorem ipsum */ },
};

export const SinDatos: Story = {
  args: { data: undefined },
};
```

**Nota sobre `render` personalizado:** si una story compone varios sub-componentes en vez de pasar
`args` directo al `component` del meta (como `Field` + `FieldLabel` + `FieldError` juntos), TypeScript
exige igual un `args` que satisfaga el tipo de props del `component` de meta — agregar
`args: { children: null }` (o el mínimo que pida el tipo) aunque no se use dentro del `render`. Ver
`shared/ui/components/field.stories.tsx`.

Ejemplos reales en el repo: `components/ui/button.stories.tsx` (variantes vía `argTypes`),
`shared/ui/components/field.stories.tsx` (composición con `render`). Mismo patrón aplica a
cualquier componente data-driven de un módulo (p.ej. `modules/ejemplo/ui/kpi-cards.stories.tsx`,
con story `ConDatos` y story `SinDatos`).

---

## 4. Theming: claro / oscuro / marca (multi-tema)

Si el proyecto tiene más de 2 temas activados por clase en un ancestro (`app/globals.css`), **ojo
con el default:** a veces `:root` (sin clase) NO es el tema claro sino un tercer tema de marca
(ej. `conatel`, `acme`, etc.) — verificar cuál es el default real antes de asumirlo, no todos los
proyectos usan `:root` = claro. `.storybook/preview.tsx` importa `app/globals.css` y agrega un
toolbar de Storybook para togglear entre todos los temas activos:

```tsx
import "../app/globals.css";

// Ejemplo con un tercer tema de marca ("brand") como default sin clase (`:root`) —
// ajustar las claves/valores a los temas reales del proyecto.
const THEME_CLASS: Record<string, string> = { light: "light", dark: "dark", brand: "" };

const withTheme: Decorator = (Story, context) => {
  const theme = String(context.globals.theme ?? "light");
  return (
    <div className={THEME_CLASS[theme] ?? ""} style={{ padding: "1.5rem" }}>
      <Story />
    </div>
  );
};
```

**Regla:** antes de dar una story por completa, togglear el selector de tema en la barra de
Storybook (ícono de pincel) y confirmar que el componente se ve bien en todos los temas activos —
no solo el default.

---

## 5. Chromatic (regresión visual)

Chromatic necesita una cuenta en [chromatic.com](https://www.chromatic.com/) y un
`CHROMATIC_PROJECT_TOKEN` — **eso es un paso manual que le corresponde al equipo**, no algo que se
resuelva desde el código. Una vez que exista el token:

```bash
CHROMATIC_PROJECT_TOKEN=xxxx pnpm chromatic
```

`--exit-zero-on-changes` (ya en el script) hace que Chromatic no rompa el pipeline solo por
detectar un cambio visual — cambios reales de diseño son esperables; lo que sí bloquea es un error
de build de Storybook.

**Regla:** el CLI de Chromatic no corre en el gate de `Dockerfile.frontend` (necesita el token +
subir capturas a un servicio externo, no cabe en el sandbox aislado de `docker build`) — es un job
de CI aparte, o se corre manualmente antes de un release de diseño.

---

## 6. Pre-flight checks

- [ ] ¿El componente nuevo tiene su `.stories.tsx` al lado, con al menos 2 variantes reales
      (no solo el estado por defecto)?
- [ ] ¿Se probó con el toolbar de tema (todos los temas activos del proyecto)?
- [ ] ¿`pnpm build-storybook` termina sin error?
- [ ] ¿`pnpm test:storybook` pasa (las stories también corren como test de Vitest en Chromium)?
- [ ] Si se tocó `.storybook/main.ts` o `preview.tsx`, ¿se corrió `pnpm format:check` y
      `pnpm typecheck` después?
