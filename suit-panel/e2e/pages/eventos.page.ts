import { Page, Locator, expect } from "@playwright/test";

export class EventosPage {
  readonly ledgerLinks: Locator;

  constructor(public readonly page: Page) {
    this.ledgerLinks = page.getByRole("link", { name: "Ver transaccion de ledger" });
  }

  async goto() {
    await this.page.goto("/eventos");
    await expect(this.page.locator("h1")).toHaveText("Eventos");
  }

  async clickPrimerLinkLedger() {
    await this.ledgerLinks.first().click();
  }
}
