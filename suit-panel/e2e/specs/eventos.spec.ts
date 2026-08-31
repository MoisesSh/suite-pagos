import { test } from "../fixtures/auth.fixture";
import { EventosPage } from "../pages/eventos.page";
import { TransaccionLedgerPage } from "../pages/transaccion-ledger.page";

test.describe("Eventos -> Transaccion de ledger", () => {
  test("click en 'Ver transaccion de ledger' navega a la transaccion vinculada", async ({ page }) => {
    const eventos = new EventosPage(page);
    await eventos.goto();

    const linkCount = await eventos.ledgerLinks.count();
    test.skip(
      linkCount === 0,
      "No hay ningun evento con transaccion_ledger_id asociado en los datos actuales del stack.",
    );

    await eventos.clickPrimerLinkLedger();

    const transaccionLedger = new TransaccionLedgerPage(page);
    await transaccionLedger.verificarCargada();
  });
});
