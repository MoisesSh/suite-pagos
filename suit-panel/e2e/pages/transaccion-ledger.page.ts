import { Page, expect } from "@playwright/test";

export class TransaccionLedgerPage {
  constructor(public readonly page: Page) {}

  async verificarCargada() {
    await expect(this.page.locator("h1")).toHaveText("Transaccion de ledger");
    await expect(this.page).toHaveURL(/\/transacciones-ledger\/[^/]+$/);
  }
}
