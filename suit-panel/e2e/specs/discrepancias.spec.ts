import { test } from "../fixtures/auth.fixture";
import { DiscrepanciasPage } from "../pages/discrepancias.page";
import { TransaccionLedgerPage } from "../pages/transaccion-ledger.page";

test.describe("Discrepancias -> Transaccion de ledger", () => {
  test("click en 'Ver transaccion de ledger' navega a la transaccion vinculada", async ({ page }) => {
    const discrepancias = new DiscrepanciasPage(page);
    await discrepancias.goto();

    const linkCount = await discrepancias.ledgerLinks.count();
    test.skip(
      linkCount === 0,
      "No hay ninguna discrepancia con transaccion_ledger_id asociado en los datos actuales del stack.",
    );

    await discrepancias.clickPrimerLinkLedger();

    const transaccionLedger = new TransaccionLedgerPage(page);
    await transaccionLedger.verificarCargada();
  });
});
