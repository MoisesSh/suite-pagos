import Link from "next/link";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import CodeBlock from "@/modules/guia/ui/code-block";

export const metadata = {
  title: "Guía de integración — Developer Portal",
};

export default function GuiaPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Guía de integración
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Para equipos de apps consumidoras (Conatel en Línea, Homologación, futuras) que quieran
          cobrar a través de la Suite Centralizada de Pagos embebiendo el formulario de cobro por
          iframe.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          Antes de empezar: tu app debe estar registrada
        </h2>
        <p className="text-sm text-muted-foreground">
          El Orquestador rechaza cualquier intento de checkout de una app/dominio no registrado —
          es un control de seguridad bloqueante, no una formalidad.
        </p>
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900"
        >
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            El registro de aplicación/dominio/proveedor lo gestiona el equipo de Conatel desde el
            panel interno — no es autogestionable desde este Developer Portal. Pedile al equipo de
            la Suite que registre tu <strong>nombre</strong>, <strong>dominio exacto</strong> (sin
            protocolo ni puerto, ej. <code>conatel.gob.ve</code>) y <strong>proveedor</strong> (hoy
            solo <code>BDV</code>). Sin ese registro, el paso 1 del flujo devuelve <code>403</code>.
          </p>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-foreground">El flujo, en 3 pasos</h2>
        <ol className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <li className="rounded-lg border border-border p-4">
            <p className="text-xs font-medium text-muted-foreground">Paso 1</p>
            <p className="mt-1 text-sm font-medium text-foreground">
              Iniciás el checkout desde tu servidor
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Server-to-server, obtenés un <code>checkout_token</code>.
            </p>
          </li>
          <li className="rounded-lg border border-border p-4">
            <p className="text-xs font-medium text-muted-foreground">Paso 2</p>
            <p className="mt-1 text-sm font-medium text-foreground">
              Embebés el formulario en un iframe
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              El pagador completa banco, cédula, teléfono y OTP.
            </p>
          </li>
          <li className="rounded-lg border border-border p-4">
            <p className="text-xs font-medium text-muted-foreground">Paso 3</p>
            <p className="mt-1 text-sm font-medium text-foreground">
              Escuchás el resultado (postMessage + webhook)
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              El webhook es tu fuente de verdad, no el mensaje del navegador.
            </p>
          </li>
        </ol>
        <Link
          href="/guia/flujo"
          className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          Ver el diagrama y el detalle de cada paso
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">Referencia rápida de endpoints</h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted text-xs font-medium text-foreground">
              <tr>
                <th className="px-4 py-2 font-medium">Endpoint</th>
                <th className="px-4 py-2 font-medium">Quién lo llama</th>
                <th className="px-4 py-2 font-medium">Desde dónde</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-mono text-xs">
                  POST /api/autorizacion/validar-acceso/
                </td>
                <td className="px-4 py-2">Tu servidor</td>
                <td className="px-4 py-2">Server-to-server</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">
                  GET /api/autorizacion/cobro/formulario/
                </td>
                <td className="px-4 py-2">El navegador del pagador</td>
                <td className="px-4 py-2">
                  <code>src</code> del iframe
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">
                  POST /api/autorizacion/cobro/otp/ y /cobro/
                </td>
                <td className="px-4 py-2">El propio formulario</td>
                <td className="px-4 py-2">Internos, no los llamás vos directo</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground">
          No necesitás llamar <code>/cobro/otp/</code> ni <code>/cobro/</code> directamente — esos
          los maneja el JavaScript del formulario que vos embebés. Tu única integración real es el
          paso 1 (servidor) y el paso 3 (escuchar el resultado).
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          Probalo ahora mismo, sin escribir código
        </h2>
        <p className="text-sm text-muted-foreground">
          El Developer Portal tiene una página que genera un <code>checkout_token</code> real y
          embebe el formulario real, con los datos de prueba de BDV QA al lado.
        </p>
        <Button className="w-fit" nativeButton={false} render={<Link href="/probar-iframe" />}>
          Probar iframe de pago
        </Button>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">Ejemplo mínimo, paso 1</h2>
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
      </section>
    </div>
  );
}
