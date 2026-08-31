import { Page, Locator, expect } from "@playwright/test";

export class DiscrepanciasPage {
  readonly ledgerLinks: Locator;

  constructor(public readonly page: Page) {
    this.ledgerLinks = page.getByRole("link", { name: "Ver transaccion de ledger" });
  }

  async goto() {
    await this.page.goto("/discrepancias");
    await expect(this.page.locator("h1")).toHaveText("Discrepancias");
    // La lista se carga client-side via SWR (skeleton -> contenido); esperar
    // a que desaparezca antes de contar links, si no la carrera da 0 falsos.
    await this.page
      .locator('[data-slot="skeleton"]')
      .first()
      .waitFor({ state: "detached", timeout: 10_000 })
      .catch(() => {});
  }

  async clickPrimerLinkLedger() {
    await this.ledgerLinks.first().click();
  }
}
