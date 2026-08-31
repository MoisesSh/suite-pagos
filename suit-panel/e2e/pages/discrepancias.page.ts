import { Page, Locator, expect } from "@playwright/test";

export class DiscrepanciasPage {
  readonly ledgerLinks: Locator;

  constructor(public readonly page: Page) {
    this.ledgerLinks = page.getByRole("link", { name: "Ver transaccion de ledger" });
  }

  async goto() {
    await this.page.goto("/discrepancias");
    await expect(this.page.locator("h1")).toHaveText("Discrepancias");
  }

  async clickPrimerLinkLedger() {
    await this.ledgerLinks.first().click();
  }
}
