---
name: formato-prettier
description: Formato de código con Prettier para este proyecto. Config, integración con ESLint, cuándo correr format vs format:check, y qué hacer si un archivo nuevo no respeta el estilo.
---

# Skill de formato con Prettier

Prettier es la única fuente de verdad del **formato** (comillas, punto y coma, ancho de línea,
comas finales). ESLint sigue siendo la fuente de verdad de **arquitectura** (`boundaries/*`) y
**calidad de código** (`import/order`, `consistent-type-imports`, reglas de React/Next). Los dos
conviven porque `eslint-config-prettier` apaga, al final de `eslint.config.mjs`, cualquier regla de
ESLint que pudiera chocar con el formato.

---

## 1. Setup (ya instalado)

```bash
pnpm add -D prettier eslint-config-prettier
```

### `.prettierrc.json` (raíz del frontend)

```json
{
  "semi": true,
  "singleQuote": false,
  "tabWidth": 2,
  "trailingComma": "all",
  "printWidth": 100
}
```

### `.prettierignore`

```
node_modules
.next
pnpm-lock.yaml
package-lock.json
tsconfig.tsbuildinfo
test-results
e2e/.auth
storybook-static
```

### `eslint.config.mjs` — debe ir al final del array

```js
import prettierConfig from "eslint-config-prettier";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  architectureBoundaries,
  sharedIsolation,
  codeStyle,
  prettierConfig, // ← siempre el último: apaga conflictos de estilo, no de arquitectura
  globalIgnores([...]),
]);
```

**Regla:** si se agrega un bloque nuevo a `eslintConfig` (otra regla de arquitectura, otro plugin),
`prettierConfig` se queda al final. Si se mueve antes de un bloque que define reglas de estilo, ese
bloque puede volver a chocar con Prettier sin que nadie lo note hasta el próximo `format:check`.

---

## 2. Scripts

```json
{
  "scripts": {
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  }
}
```

- `pnpm format` — reescribe archivos. Úsalo en local antes de un commit grande, o una sola vez al
  adoptar Prettier en un repo que no lo tenía (diff grande, pero solo de formato).
- `pnpm format:check` — no modifica nada, solo falla si algo no está formateado. Es el que corre en
  el gate de `Dockerfile.frontend` (stage `tester`) — si falla ahí, el build no llega a producción.

---

## 3. Flujo de trabajo

1. Escribe el código como te resulte natural — no formatees a mano.
2. Antes de terminar una tarea, corre `pnpm format` (o deja que el editor lo haga on-save con la
   extensión de Prettier).
3. Si tocaste `eslint.config.mjs` o cualquier regla de estilo, corre `pnpm format:check` para
   confirmar que no quedó nada sin formatear antes de dar la tarea por completa.
4. Si `eslint --fix` y `prettier --write` se corren en el mismo archivo, el orden que evita
   pisarse es: primero `eslint --fix` (reordena imports, agrega `import type`), después
   `prettier --write` (ajusta espacios/comillas sobre el resultado ya reordenado).

```bash
npx eslint . --fix
npx prettier --write .
pnpm format:check   # debe salir "All matched files use Prettier code style!"
```

---

## 4. Qué NO tocar con Prettier

- Archivos en `.prettierignore` (lockfiles, `.next/`, artefactos de build).
- No agregar reglas de estilo manuales a `eslint.config.mjs` que dupliquen lo que ya hace Prettier
  (ancho de línea, comillas) — eso es exactamente lo que `eslint-config-prettier` existe para evitar.
- No usar `// prettier-ignore` para "arreglar" algo que en realidad es un error de lint real
  (`boundaries/dependencies`, `import/order`) — esos no los resuelve Prettier, hay que corregir el
  import de verdad.

---

## 5. Pre-flight checks

- [ ] ¿`pnpm format:check` pasa en 0 diffs?
- [ ] ¿`prettierConfig` sigue siendo el último elemento del array en `eslint.config.mjs`?
- [ ] ¿Los archivos nuevos (`*.stories.tsx`, `*.test.ts`, configs) están en `.prettierignore` solo
      si de verdad no deben formatearse — o si no, ya pasaron por `pnpm format`?
- [ ] ¿`pnpm typecheck` y `pnpm build` siguen en verde después de un `pnpm format` masivo? (Prettier
      no debería romper nada — solo espacios y comillas — pero se verifica igual).
