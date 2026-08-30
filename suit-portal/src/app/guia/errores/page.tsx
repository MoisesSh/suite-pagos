import Link from "next/link";
import { ArrowRight, ShieldAlert } from "lucide-react";

export const metadata = {
  title: "Errores y ambiente QA — Guía de integración",
};

const CODIGOS = [
  { codigo: "1013", descripcion: "Monto inválido." },
  {
    codigo: "1026 / 1094",
    descripcion:
      "Referencia/operación duplicada — tratalo como posible duplicado de tu lado, no como error de negocio a mostrar tal cual.",
  },
  { codigo: "1061", descripcion: "Monto supera el límite diario del pagador." },
  { codigo: "1080", descripcion: "Documento de identidad inválido." },
];

export default function ErroresPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Errores y ambiente QA
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          <code>pago.error</code> puede traer, dentro de <code>detalle</code>, un{" "}
          <code>codigo_proveedor</code> con el código real de BDV. Estos son los más comunes en
          integración (tabla completa en el PDF del proveedor):
        </p>
      </div>

      <section className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted text-xs font-medium text-foreground">
            <tr>
              <th className="px-4 py-2 font-medium">Código</th>
              <th className="px-4 py-2 font-medium">Significado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {CODIGOS.map((c) => (
              <tr key={c.codigo}>
                <td className="px-4 py-2 font-mono text-xs whitespace-nowrap">{c.codigo}</td>
                <td className="px-4 py-2">{c.descripcion}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-foreground">Ambiente de prueba (QA/dummy)</h2>
        <p className="text-sm text-muted-foreground">
          Mientras el proveedor esté en modo QA (no producción),{" "}
          <strong>solo funcionan valores exactos documentados</strong>, no cualquier dato de
          prueba:
        </p>
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-border p-3">
            <dt className="text-xs text-muted-foreground">Cédula</dt>
            <dd className="font-mono text-sm text-foreground">V12345678</dd>
          </div>
          <div className="rounded-lg border border-border p-3">
            <dt className="text-xs text-muted-foreground">Teléfono</dt>
            <dd className="font-mono text-sm text-foreground">04125692243</dd>
          </div>
          <div className="rounded-lg border border-border p-3">
            <dt className="text-xs text-muted-foreground">Banco</dt>
            <dd className="font-mono text-sm text-foreground">0102 (BDV, único disponible hoy)</dd>
          </div>
          <div className="rounded-lg border border-border p-3">
            <dt className="text-xs text-muted-foreground">OTP</dt>
            <dd className="font-mono text-sm text-foreground">5551111</dd>
          </div>
        </dl>
        <Link
          href="/probar-iframe"
          className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          Probar el flujo completo embebido de verdad, con estos mismos datos
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </section>

      <section
        role="status"
        className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900"
      >
        <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>
          <strong>Quirk conocido del ambiente QA (no es un bug de este servicio):</strong> el
          dummy de BDV solo reconoce el monto de ejemplo del PDF (<code>1000.6</code>, un decimal)
          de forma literal — un monto real con 2 decimales (<code>1000.60</code>, el formato
          correcto de producción) puede devolver el código <code>1001</code> no documentado por ese
          ambiente. En producción real esto no debería reproducirse.
        </p>
      </section>
    </div>
  );
}
