import { ShieldAlert } from "lucide-react";
import CodeBlock from "@/modules/guia/ui/code-block";

export const metadata = {
  title: "Webhook server-to-server — Guía de integración",
};

export default function WebhooksPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Webhook server-to-server (fuente de verdad primaria)
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Igual que Stripe, Mercado Pago, PayPal, Culqi y dLocal, el Orquestador te notifica el
          resultado del cobro directo a tu servidor — sin depender de que el navegador del pagador
          siga abierto.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">Configurarlo</h2>
        <p className="text-sm text-muted-foreground">
          Seteá <code>webhook_url</code> al registrar o editar tu aplicación (misma API admin del
          registro, gestionada por el equipo de Conatel):
        </p>
        <CodeBlock
          filename="PATCH /api/autorizacion/admin/aplicaciones/<id>/"
          lang="json"
          code={`{"webhook_url": "https://tu-servidor.gob.ve/webhooks/suit-pagos"}`}
        />
        <p className="text-sm text-muted-foreground">
          Al setearla por primera vez, el Orquestador genera automáticamente un{" "}
          <code>webhook_secret</code> — <strong>nunca lo mandes vos ni lo elijas a mano</strong>,
          es la clave HMAC con la que se firma cada entrega. Guardalo de forma segura, es
          equivalente al &quot;signing secret&quot; del dashboard de Stripe.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">Qué vas a recibir</h2>
        <CodeBlock
          filename="POST https://tu-servidor.gob.ve/webhooks/suit-pagos"
          lang="http"
          code={`Content-Type: application/json
X-Suit-Signature: sha256=<hmac_sha256_hex>

{"event_id": "...", "event_type": "pago.confirmado", "schema_version": 1, "payload": {...}}`}
        />
        <p className="text-sm text-muted-foreground">
          Mismo <code>payload</code> que el evento que el Orquestador publica a RabbitMQ para
          Conciliación — <code>pago_id</code>, <code>monto</code>, <code>moneda_codigo</code>,{" "}
          <code>referencia_corta</code>, <code>estado</code>, etc.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          Validar la firma (obligatorio antes de confiar en el payload)
        </h2>
        <p className="text-sm text-muted-foreground">
          La firma es HMAC-SHA256 sobre el <strong>body exacto recibido</strong> (los bytes crudos,
          no un JSON re-serializado) con tu <code>webhook_secret</code>.
        </p>
        <CodeBlock
          filename="Python"
          lang="python"
          code={`import hashlib
import hmac

def validar_firma(cuerpo_crudo: bytes, header_signature: str, webhook_secret: str) -> bool:
    firma_esperada = 'sha256=' + hmac.new(
        webhook_secret.encode('utf-8'), cuerpo_crudo, hashlib.sha256,
    ).hexdigest()
    # compare_digest, nunca \`==\` — evita timing attacks al comparar la firma.
    return hmac.compare_digest(header_signature, firma_esperada)`}
        />
        <CodeBlock
          filename="Node.js"
          lang="javascript"
          code={`const crypto = require('crypto');

function validarFirma(cuerpoCrudo, headerSignature, webhookSecret) {
  const firmaEsperada = 'sha256=' + crypto
    .createHmac('sha256', webhookSecret)
    .update(cuerpoCrudo)
    .digest('hex');
  return crypto.timingSafeEqual(Buffer.from(headerSignature), Buffer.from(firmaEsperada));
}`}
        />
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900"
        >
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            Leé el body como bytes crudos antes de parsearlo a JSON (en Express, por ejemplo,
            necesitás <code>express.raw()</code> para esta ruta específica, no{" "}
            <code>express.json()</code>, para poder recalcular la firma sobre los bytes exactos).
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          Respondé <strong>2xx</strong> apenas hayas validado la firma y encolado tu propio
          procesamiento — no hagas trabajo pesado sincrónico antes de responder. El Orquestador
          reintenta con backoff fijo si no recibís 2xx, hasta un tope configurable de intentos, y
          después deja de reintentar (<code>agotado</code>) sin otro aviso más que ese estado
          interno.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">Idempotencia de tu lado</h2>
        <p className="text-sm text-muted-foreground">
          El mismo <code>event_id</code> puede llegarte más de una vez (entrega{" "}
          <em>at-least-once</em>, igual que el resto del sistema) — dedupealo por{" "}
          <code>event_id</code> antes de procesar, no asumas que un webhook se entrega exactamente
          una vez.
        </p>
      </section>
    </div>
  );
}
