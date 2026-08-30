import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

test.describe("Accesibilidad", () => {
  for (const ruta of [
    "/",
    "/documentacion",
    "/probar-iframe",
    "/guia",
    "/guia/flujo",
    "/guia/webhooks",
    "/guia/errores",
  ]) {
    test(`${ruta} no tiene violaciones de accesibilidad`, async ({ page }) => {
      await page.goto(ruta);
      const resultados = await new AxeBuilder({ page }).analyze();
      expect(resultados.violations).toEqual([]);
    });
  }
});
