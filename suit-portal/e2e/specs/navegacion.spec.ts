import { test, expect } from "@playwright/test";

test.describe("Navegación", () => {
  test("el nav enlaza a inicio, documentación y registro", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation");
    await nav.getByRole("link", { name: "Documentación" }).click();
    await expect(page).toHaveURL("/documentacion");

    await nav.getByRole("link", { name: "Registrar aplicación" }).click();
    await expect(page).toHaveURL("/aplicaciones/nueva");
  });

  test("/documentacion muestra el aviso de que el Orquestador no expone Swagger", async ({
    page,
  }) => {
    await page.goto("/documentacion");
    await expect(page.getByRole("status")).toContainText("suit-orquestador");
  });
});
