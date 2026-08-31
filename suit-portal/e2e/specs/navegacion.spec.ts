import { test, expect } from "@playwright/test";

test.describe("Navegación", () => {
  test("el nav enlaza a inicio, guía, documentación y prueba de iframe", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation").first();

    await nav.getByRole("link", { name: "Guía de integración" }).click();
    await expect(page).toHaveURL("/guia");

    await nav.getByRole("link", { name: "Documentación" }).click();
    await expect(page).toHaveURL("/documentacion");

    await nav.getByRole("link", { name: "Probar iframe de pago" }).click();
    await expect(page).toHaveURL("/probar-iframe");
  });

  test("no queda ningún enlace de registro de aplicaciones (se movió a suit-panel)", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: /registrar aplicaci[oó]n/i })).toHaveCount(0);
  });

  test("el sidebar de /guia navega entre sus secciones", async ({ page }) => {
    await page.goto("/guia");
    const sidebar = page.getByRole("navigation", { name: "Secciones de la guía de integración" });

    await sidebar.getByRole("link", { name: "El flujo (3 pasos)" }).click();
    await expect(page).toHaveURL("/guia/flujo");

    await sidebar.getByRole("link", { name: "Webhook server-to-server" }).click();
    await expect(page).toHaveURL("/guia/webhooks");

    await sidebar.getByRole("link", { name: "Errores y ambiente QA" }).click();
    await expect(page).toHaveURL("/guia/errores");
  });

  test("/documentacion enlaza a la guía de integración", async ({ page }) => {
    await page.goto("/documentacion");
    await page
      .getByRole("status")
      .getByRole("link", { name: "guía de integración" })
      .click();
    await expect(page).toHaveURL("/guia");
  });
});
