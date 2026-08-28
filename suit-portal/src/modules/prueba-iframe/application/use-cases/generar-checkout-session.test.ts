import { describe, expect, it, vi } from "vitest";
import type {
  CheckoutSessionResult,
  RepoCheckoutSession,
} from "../../domain/ports/repo-checkout-session";
import { generarCheckoutDePrueba } from "./generar-checkout-session";

function fakeRepo(result: CheckoutSessionResult): RepoCheckoutSession {
  return { generar: vi.fn().mockResolvedValue(result) };
}

describe("generarCheckoutDePrueba", () => {
  it("pasa los datos de prueba fijos (dominio localhost, proveedor BDV) al repo", async () => {
    const repo = fakeRepo({ status: "ok", checkoutToken: "tok-123" });
    await generarCheckoutDePrueba(repo);
    expect(repo.generar).toHaveBeenCalledWith({
      dominio: "localhost",
      proveedor: "BDV",
      monto: "1000.60",
      moneda: "VES",
      concepto: "Pago",
    });
  });

  it("propaga un resultado ok sin perder el checkoutToken", async () => {
    const repo = fakeRepo({ status: "ok", checkoutToken: "tok-abc" });
    const result = await generarCheckoutDePrueba(repo);
    expect(result).toEqual({ status: "ok", checkoutToken: "tok-abc" });
  });

  it("propaga un rechazo de negocio con su motivo", async () => {
    const repo = fakeRepo({ status: "rechazado", motivo: "dominio_no_registrado" });
    const result = await generarCheckoutDePrueba(repo);
    expect(result).toEqual({ status: "rechazado", motivo: "dominio_no_registrado" });
  });

  it("propaga un error de transporte", async () => {
    const repo = fakeRepo({ status: "error" });
    const result = await generarCheckoutDePrueba(repo);
    expect(result).toEqual({ status: "error" });
  });
});
