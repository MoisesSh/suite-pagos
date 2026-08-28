import { test, expect } from "@playwright/test";

// Contra el stub de e2e/mocks/orquestador-stub.mjs — ver playwright.config.ts.
test.describe("Probar iframe de pago", () => {
  test("muestra el iframe con un checkout_token y los datos de prueba documentados", async ({
    page,
  }) => {
    await page.goto("/probar-iframe");
    await expect(page.locator("h1")).toContainText("Probar iframe de pago");

    const iframe = page.frameLocator("iframe[title='Formulario de cobro BDV Pago Móvil C2P']");
    await expect(iframe.getByTestId("stub-checkout-token")).toContainText("stub-checkout-token-");

    await expect(page.getByText("Banco de Venezuela")).toBeVisible();
    await expect(page.getByText("V12345678")).toBeVisible();
    await expect(page.getByText("04125692243")).toBeVisible();
  });

  test("pide un checkout_token nuevo en cada carga (no cachea)", async ({ page }) => {
    await page.goto("/probar-iframe");
    const primerToken = await page
      .frameLocator("iframe[title='Formulario de cobro BDV Pago Móvil C2P']")
      .getByTestId("stub-checkout-token")
      .textContent();

    await page.reload();
    const segundoToken = await page
      .frameLocator("iframe[title='Formulario de cobro BDV Pago Móvil C2P']")
      .getByTestId("stub-checkout-token")
      .textContent();

    expect(segundoToken).not.toBe(primerToken);
  });

  test("muestra el aviso de que solo funciona accediendo por localhost", async ({ page }) => {
    await page.goto("/probar-iframe");
    await expect(page.getByRole("status")).toContainText("http://localhost");
  });
});
