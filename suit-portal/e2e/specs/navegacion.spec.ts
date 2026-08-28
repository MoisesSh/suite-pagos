import { test, expect } from "@playwright/test";

test.describe("Navegación", () => {
  test("el nav enlaza a inicio, documentación, registro y prueba de iframe", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation");
    await nav.getByRole("link", { name: "Documentación" }).click();
    await expect(page).toHaveURL("/documentacion");

    await nav.getByRole("link", { name: "Registrar aplicación" }).click();
    await expect(page).toHaveURL("/aplicaciones/nueva");

    await nav.getByRole("link", { name: "Probar iframe de pago" }).click();
    await expect(page).toHaveURL("/probar-iframe");
  });

  test("/documentacion muestra el aviso de que el Orquestador no expone Swagger", async ({
    page,
  }) => {
    await page.goto("/documentacion");
    await expect(page.getByRole("status")).toContainText("suit-orquestador");
  });
});
