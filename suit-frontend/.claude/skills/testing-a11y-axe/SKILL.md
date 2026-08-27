---
name: testing-a11y-axe
description: Accesibilidad automática con @axe-core/playwright. Cómo agregar una verificación de a11y a una ruta nueva, reusando el Playwright que ya existe (fixtures, auth, navegadores).
---

# Skill de accesibilidad con axe-core

No es infraestructura nueva: `@axe-core/playwright` corre **dentro** de la suite de Playwright que
ya existe (ver skill `testing-e2e-playwright`) — reusa `e2e/fixtures/auth.fixture.ts` para las rutas
protegidas y el `playwright.config.ts` ya configurado (Chromium + Firefox + WebKit).

---

## 1. Setup (ya instalado)

```bash
pnpm add -D @axe-core/playwright
```

Storybook también trae su propio addon de a11y (`@storybook/addon-a11y`, ver skill
`storybook-chromatic`) — ese chequea accesibilidad **por componente aislado** durante el desarrollo;
esta skill chequea **la página completa renderizada**, con datos reales, en el navegador de verdad.
Son complementarios, no redundantes.

---

## 2. Patrón

```ts
// e2e/specs/accesibilidad.spec.ts
import AxeBuilder from "@axe-core/playwright";
import { test as base, expect } from "@playwright/test";

import { test as authTest } from "../fixtures/auth.fixture";

base.describe("Accesibilidad - rutas públicas", () => {
  base("/login no tiene violaciones de accesibilidad", async ({ page }) => {
    await page.goto("/login");
    const resultados = await new AxeBuilder({ page }).analyze();
    expect(resultados.violations).toEqual([]);
  });
});

authTest.describe("Accesibilidad - rutas protegidas", () => {
  authTest("/inicio no tiene violaciones de accesibilidad", async ({ authPage }) => {
    await authPage.goto("/inicio");
    const resultados = await new AxeBuilder({ page: authPage }).analyze();
    expect(resultados.violations).toEqual([]);
  });
});
```

**Regla:** usar `base`/`authTest` como el alias del `test` importado — nunca reusar el nombre
genérico `test` para ambos, porque `test.describe` de uno no es el mismo `describe` del otro (son
instancias `test.extend()` distintas) y el error queda silencioso hasta que TypeScript se queja.

---

## 3. Cuándo agregar un caso nuevo

**Regla:** toda ruta nueva bajo `app/(app)/` o `app/(auth)/` que tenga su propio Page Object en
`e2e/pages/` (por convención de `testing-e2e-playwright`) DEBE tener también una verificación de
accesibilidad en `e2e/specs/accesibilidad.spec.ts`, en el bloque que corresponda (pública vs.
protegida).

---

## 4. Qué hacer con una violación real

1. Correr `pnpm test:e2e:chromium -- accesibilidad` y leer el reporte — cada violación trae
   `id`, `impact` (`minor`/`moderate`/`serious`/`critical`), `nodes` (selector exacto) y un link a
   la regla de axe-core.
2. Arreglar en el componente real (contraste de color, `aria-label` faltante, orden de foco) — no
   silenciar con un selector de exclusión salvo que sea un falso positivo confirmado (p. ej. un
   ícono puramente decorativo que ya tiene `aria-hidden`).
3. Si el ruido inicial de una página es alto y bloquea todo el resto del trabajo, se puede acotar
   temporalmente por impacto:
   ```ts
   const resultados = await new AxeBuilder({ page }).analyze();
   const graves = resultados.violations.filter(
     (v) => v.impact === "serious" || v.impact === "critical",
   );
   expect(graves).toEqual([]);
   ```
   Esto es un escalón temporal, no el estado final — el objetivo es `violations` vacío sin filtrar.

---

## 5. Pre-flight checks

- [ ] ¿La ruta nueva tiene su caso en `e2e/specs/accesibilidad.spec.ts`?
- [ ] ¿Usa `authTest`/`authPage` si la ruta requiere sesión, o `base`/`page` si es pública?
- [ ] ¿Corriste `pnpm test:e2e:chromium -- accesibilidad` con la app levantada al menos una vez
      para esa ruta antes de dar la tarea por completa?
- [ ] ¿Ninguna violación quedó silenciada sin una razón documentada en el propio test?
