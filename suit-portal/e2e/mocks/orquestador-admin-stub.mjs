// Stub hermético del endpoint admin de suit-orquestador para E2E.
// No es un mock de la app — simula el CONTRATO real documentado en
// CONTRATO-API-ACTUAL.md (seccion "Admin — registro de apps/dominios") para
// que los tests de Playwright ejerciten el codigo de integracion real
// (URL, header Authorization, body, mapeo de 201/400/401) sin depender de
// que suit-orquestador este corriendo.
import { createServer } from "node:http";

const PORT = 4100;
const EXPECTED_TOKEN = "test-token-e2e";
const DOMINIO_DUPLICADO = "ya-registrado.gob.ve";

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

const server = createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    return json(res, 200, { ok: true });
  }

  if (req.method === "POST" && req.url === "/api/autorizacion/admin/aplicaciones/") {
    const auth = req.headers.authorization;
    if (auth !== `Token ${EXPECTED_TOKEN}`) {
      return json(res, 401, { detail: "Invalid token." });
    }

    const body = JSON.parse((await readBody(req)) || "{}");

    if (body.dominio === DOMINIO_DUPLICADO) {
      return json(res, 400, { dominio: ["Ya existe una aplicación con este dominio."] });
    }

    return json(res, 201, {
      id: "b7e5c9c0-0000-4000-8000-000000000001",
      nombre: body.nombre,
      dominio: body.dominio,
      proveedor: body.proveedor,
    });
  }

  json(res, 404, { detail: "not found (stub)" });
});

server.listen(PORT, () => {
  console.log(`[stub] orquestador admin stub listening on :${PORT}`);
});
