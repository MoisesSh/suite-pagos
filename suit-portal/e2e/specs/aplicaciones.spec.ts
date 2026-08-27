import { test, expect } from "@playwright/test";
import { AplicacionesPage } from "../pages/aplicaciones.page";

test.describe("Registro de aplicación (mockeado)", () => {
  let page: AplicacionesPage;

  test.beforeEach(async ({ page: p }) => {
    page = new AplicacionesPage(p);
    await page.goto();
  });

  test("muestra el aviso de que el backend real no existe todavía", async () => {
    await page.verAvisoDeMock();
  });

  test("valida campos requeridos antes de enviar", async ({ page: p }) => {
    await p.getByRole("button", { name: "Enviar solicitud" }).click();
    await expect(p.getByText("Mínimo 2 caracteres")).toBeVisible();
  });

  test("envía el formulario y muestra el mensaje simulado de éxito", async () => {
    await page.enviar({
      nombre: "Conatel en Línea",
      dominio: "conatel-en-linea.gob.ve",
      proveedor: "BDV",
    });
    await page.verMensajeSimulado();
  });
});
