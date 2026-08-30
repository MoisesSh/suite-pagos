// Stub hermético de suit-orquestador para E2E. No es un mock de la app — simula
// el CONTRATO real (ver CONTRATO-API-ACTUAL.md y el código real de
// apps/autorizacion) para que los tests de Playwright ejerciten el código de
// integración real (URL, headers, body, mapeo de respuestas) sin depender de
// que suit-orquestador esté corriendo.
import { createServer } from "node:http";

const PORT = 4100;

let checkoutTokenCounter = 0;

function readBody(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => resolve(raw));
    req.on("error", reject);
  });
}

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

function html(res, status, body) {
  res.writeHead(status, { "Content-Type": "text/html" });
  res.end(body);
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (req.method === "GET" && url.pathname === "/health") {
    return json(res, 200, { ok: true });
  }

  if (req.method === "POST" && url.pathname === "/api/autorizacion/validar-acceso/") {
    const body = JSON.parse((await readBody(req)) || "{}");

    if (body.dominio !== "localhost" || body.proveedor !== "BDV") {
      return json(res, 403, { autorizado: false, motivo: "dominio_no_registrado" });
    }

    checkoutTokenCounter += 1;
    return json(res, 200, {
      autorizado: true,
      aplicacion: "Desarrollo Local",
      checkout_token: `stub-checkout-token-${checkoutTokenCounter}`,
    });
  }

  if (req.method === "GET" && url.pathname === "/api/autorizacion/cobro/formulario/") {
    const checkoutToken = url.searchParams.get("checkout_token") ?? "";
    return html(
      res,
      200,
      `<!doctype html><html><body><p data-testid="stub-checkout-token">${checkoutToken}</p></body></html>`,
    );
  }

  json(res, 404, { detail: "not found (stub)" });
});

server.listen(PORT, () => {
  console.log(`[stub] orquestador stub listening on :${PORT}`);
});
