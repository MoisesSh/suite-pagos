import { describe, expect, it } from "vitest";
import { aplicacionFormSchema } from "./schema-aplicacion";

describe("aplicacionFormSchema", () => {
  it("acepta datos válidos", () => {
    const result = aplicacionFormSchema.safeParse({
      nombre: "Conatel en Línea",
      dominio: "conatel-en-linea.gob.ve",
      proveedor: "BDV",
    });
    expect(result.success).toBe(true);
  });

  it("rechaza un dominio sin TLD", () => {
    const result = aplicacionFormSchema.safeParse({
      nombre: "Conatel en Línea",
      dominio: "localhost",
      proveedor: "BDV",
    });
    expect(result.success).toBe(false);
  });

  it("rechaza un dominio con label vacío (doble punto)", () => {
    const result = aplicacionFormSchema.safeParse({
      nombre: "Conatel en Línea",
      dominio: "conatel..gob.ve",
      proveedor: "BDV",
    });
    expect(result.success).toBe(false);
  });

  it("rechaza un proveedor fuera del catálogo cerrado", () => {
    const result = aplicacionFormSchema.safeParse({
      nombre: "Conatel en Línea",
      dominio: "conatel-en-linea.gob.ve",
      proveedor: "MERCANTIL",
    });
    expect(result.success).toBe(false);
  });

  it("rechaza un nombre demasiado corto", () => {
    const result = aplicacionFormSchema.safeParse({
      nombre: "A",
      dominio: "conatel-en-linea.gob.ve",
      proveedor: "BDV",
    });
    expect(result.success).toBe(false);
  });
});
