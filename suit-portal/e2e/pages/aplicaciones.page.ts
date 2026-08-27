import { expect, type Page } from "@playwright/test";

export class AplicacionesPage {
  constructor(public readonly page: Page) {}

  async goto() {
    await this.page.goto("/aplicaciones/nueva");
    await expect(this.page.locator("h1")).toContainText("Registrar aplicación");
  }

  /**
   * `.fill()` en el primer campo interactuado puede perderse en WebKit: si
   * React todavía no hidrató el input controlado por RHF cuando Playwright
   * setea `.value` + dispara `input`, el commit de hidratación lo pisa de
   * vuelta a `""` (defaultValues). Se reintenta hasta que el valor persiste,
   * en vez de agregar un `waitForTimeout` a ciegas.
   */
  private async fillAndVerify(locator: ReturnType<Page["getByLabel"]>, value: string) {
    await expect(async () => {
      await locator.click();
      await locator.pressSequentially(value, { delay: 10 });
      await expect(locator).toHaveValue(value);
    }).toPass({ timeout: 10_000 });
  }

  async verAvisoDeMock() {
    await expect(this.page.getByRole("status")).toContainText(
      "no está conectado a ningún backend real",
    );
  }

  async enviar(data: { nombre: string; dominio: string; proveedor: string }) {
    await this.fillAndVerify(this.page.getByLabel("Nombre de la aplicación"), data.nombre);
    await this.fillAndVerify(this.page.getByLabel("Dominio autorizado"), data.dominio);
    await this.page.getByLabel("Proveedor de pago").click();
    await this.page.getByRole("option", { name: data.proveedor }).click();
    await this.page.getByRole("button", { name: "Enviar solicitud" }).click();
  }

  async verMensajeSimulado() {
    await expect(this.page.getByText(/registrada \(simulada\)/i)).toBeVisible();
  }
}
