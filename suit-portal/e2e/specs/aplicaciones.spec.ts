import { test, expect } from "@playwright/test";
import { AplicacionesPage } from "../pages/aplicaciones.page";

// Estos tests hablan con el stub de e2e/mocks/orquestador-admin-stub.mjs
// (levantado como webServer en playwright.config.ts), no con un backend
// mockeado dentro de la app — la app llama al endpoint real de
// suit-orquestador, el stub simula ese contrato.
test.describe("Registro de aplicación", () => {
  let page: AplicacionesPage;

  test.beforeEach(async ({ page: p }) => {
    page = new AplicacionesPage(p);
    await page.goto();
  });

  test("valida campos requeridos antes de enviar", async ({ page: p }) => {
    await p.getByRole("button", { name: "Enviar solicitud" }).click();
    await expect(p.getByText("Mínimo 2 caracteres")).toBeVisible();
  });

  test("envía el formulario y registra la aplicación en suit-orquestador", async () => {
    await page.enviar({
      nombre: "Conatel en Línea",
      dominio: "conatel-en-linea.gob.ve",
      proveedor: "BDV",
    });
    await page.verMensajeExito();
  });

  test("muestra el error real de DRF cuando el dominio ya está registrado", async () => {
    await page.enviar({
      nombre: "Conatel en Línea",
      dominio: "ya-registrado.gob.ve",
      proveedor: "BDV",
    });
    await page.verErrorDominioDuplicado();
  });
});
