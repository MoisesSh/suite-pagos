import { ShieldAlert } from "lucide-react";
import CodeBlock from "@/modules/guia/ui/code-block";
import FlowDiagram, { type FlowStep } from "@/modules/guia/ui/flow-diagram";

export const metadata = {
  title: "El flujo (3 pasos) — Guía de integración",
};

const PASOS: FlowStep[] = [
  { de: "servidor", a: "orquestador", texto: "POST /api/autorizacion/validar-acceso/ (server-to-server)" },
  { de: "orquestador", a: "servidor", texto: "checkout_token (firmado, vence en 15 minutos)" },
  { de: "servidor", a: "navegador", texto: 'Renderiza <iframe src=".../formulario/?checkout_token=...">' },
  { de: "navegador", a: "orquestador", texto: "GET /api/autorizacion/cobro/formulario/" },
  { de: "orquestador", a: "navegador", texto: "HTML del formulario (banco, cédula, teléfono, OTP)" },
  { de: "navegador", a: "orquestador", texto: "El pagador completa el formulario (OTP real vía BDV)" },
  { de: "orquestador", a: "navegador", texto: "postMessage({ type, version, payload }, tuOrigenExacto)" },
  { de: "navegador", a: "servidor", texto: "Tu JS escucha el mensaje en la ventana padre y reacciona" },
];

export default function FlujoPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">El flujo (3 pasos)</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Diagrama de secuencia completo, seguido del detalle técnico de cada paso.
        </p>
      </div>

      <FlowDiagram steps={PASOS} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          Paso 1 — Iniciar el checkout (server-side, nunca desde el navegador)
        </h2>
        <p className="text-sm text-muted-foreground">
          <code>monto</code>/<code>moneda</code>/<code>concepto</code> quedan atados
          criptográficamente dentro del <code>checkout_token</code> en este paso — es la garantía
          de que nadie puede alterar el monto a cobrar editando el HTML o la URL del iframe más
          adelante. Tu backend es quien sabe cuánto factura, así que es quien debe iniciar el
          checkout.
        </p>
        <CodeBlock
          filename="POST /api/autorizacion/validar-acceso/"
          lang="json"
          code={`{
  "dominio": "tu-dominio.gob.ve",
  "proveedor": "BDV",
  "monto": "1000.60",
  "moneda": "VES",
  "concepto": "Descripción legible para el pagador"
}`}
        />
        <CodeBlock
          filename="200 OK"
          lang="json"
          code={`{"autorizado": true, "aplicacion": "Tu App", "checkout_token": "<opaco, firmado>"}`}
        />
        <CodeBlock
          filename="403 Forbidden"
          lang="json"
          code={`{"autorizado": false, "motivo": "dominio_no_registrado"}`}
        />
        <p className="text-xs text-muted-foreground">
          Motivos posibles: <code>dominio_no_registrado</code>, <code>dominio_inactivo</code>,{" "}
          <code>aplicacion_inactiva</code>, <code>proveedor_no_encontrado</code>,{" "}
          <code>proveedor_no_autorizado</code>. El <code>checkout_token</code> vence a los 15
          minutos — generalo justo antes de mostrar la página con el iframe, no lo cachees ni lo
          reutilices entre sesiones.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          Paso 2 — Embeber el iframe (client-side)
        </h2>
        <CodeBlock
          filename="HTML"
          lang="html"
          code={`<iframe
  src="https://<host-del-orquestador>/api/autorizacion/cobro/formulario/?checkout_token=<el_token_del_paso_1>"
  width="420" height="480">
</iframe>`}
        />
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900"
        >
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            <strong>Requisito de seguridad, no opcional:</strong> tu página debe servirse
            exactamente desde el dominio que registraste — el Orquestador arma un{" "}
            <code>Content-Security-Policy: frame-ancestors</code> dinámico que solo permite ese
            dominio exacto. Si tu página corre en <code>file://</code>, en un dominio distinto, o
            en <code>localhost</code> sin haber registrado <code>localhost</code>, el navegador
            bloquea el iframe (ícono de imagen rota) — no es un bug del servicio.
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          El formulario le pide al pagador: banco afiliado a Pago Móvil (selector, poblado del
          catálogo real de bancos soportados), cédula, teléfono, y luego el OTP. Vos no controlás
          ni ves esos datos — viajan directo entre el navegador del pagador y el Orquestador.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          Paso 3 — Escuchar el resultado (postMessage)
        </h2>
        <CodeBlock
          filename="JavaScript"
          lang="javascript"
          code={`window.addEventListener('message', function (evento) {
  // Validá SIEMPRE el origen — nunca proceses un mensaje sin esto.
  if (evento.origin !== 'https://<host-del-orquestador>') return;

  var mensaje = evento.data; // { type, version, payload }

  if (mensaje.type === 'pago.completado') {
    // mensaje.payload = { pago_id, estado, referencia_corta }
    // El cobro se ejecutó. estado === "capturado" es éxito.
  }

  if (mensaje.type === 'pago.error') {
    // mensaje.payload = { status, detalle }
    // El cobro falló o fue rechazado por el proveedor.
  }
});`}
        />
        <p className="text-sm text-muted-foreground">
          El Orquestador solo manda el <code>postMessage</code> a tu origen exacto, nunca con{" "}
          <code>targetOrigin: &apos;*&apos;</code> — si por alguna razón no pudo determinar tu
          origen (Origin y Referer ausentes en la petición del iframe), simplemente no manda nada.
        </p>
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900"
        >
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            <strong>El postMessage es UX, no tu fuente de verdad.</strong> Si el navegador del
            pagador se cierra, pierde la conexión, o el mensaje no llega por cualquier motivo, tu
            app nunca se entera por esta vía. La confirmación real y autoritativa es el{" "}
            <a href="/guia/webhooks" className="underline underline-offset-2">
              webhook server-to-server
            </a>{" "}
            — usá el <code>postMessage</code> solo para redirigir/actualizar la pantalla más rápido
            mientras el pagador sigue ahí.
          </p>
        </div>
      </section>
    </div>
  );
}
