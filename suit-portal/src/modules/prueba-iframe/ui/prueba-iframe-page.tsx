import { TriangleAlert } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ORQUESTADOR_PUBLIC_URL } from "@/shared/commons/api";
import type { CheckoutSessionResult } from "../domain/ports/repo-checkout-session";

const MOTIVO_LABELS: Record<string, string> = {
  dominio_no_registrado: "El dominio 'localhost' no está registrado como DominioPermitido en el Orquestador.",
  dominio_inactivo: "El dominio 'localhost' está registrado pero inactivo.",
  aplicacion_inactiva: "La aplicación 'Desarrollo Local' está registrada pero inactiva.",
  proveedor_no_encontrado: "El proveedor BDV no existe en el catálogo del Orquestador.",
  proveedor_no_autorizado: "La aplicación 'Desarrollo Local' no tiene a BDV autorizado como proveedor.",
};

export default function PruebaIframePage({ resultado }: { resultado: CheckoutSessionResult }) {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Probar iframe de pago
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Formulario de cobro real de suit-orquestador, embebido tal como lo haría una app
          consumidora.
        </p>
      </div>

      <div
        role="status"
        className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
      >
        <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>
          Esta prueba solo funciona si accedés al Developer Portal por{" "}
          <code className="rounded bg-background/60 px-1 py-0.5 text-foreground">
            http://localhost:&lt;puerto&gt;
          </code>
          : el Orquestador valida el <code>Origin</code>/<code>Referer</code> del embebedor
          contra el dominio registrado de la app de prueba (&quot;Desarrollo Local&quot;), que es
          exactamente <code>localhost</code>, sin puerto. Por IP o por otro hostname, el
          Orquestador rechaza el embebido.
        </p>
      </div>

      {resultado.status === "rechazado" && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            El Orquestador rechazó la solicitud de checkout ({resultado.motivo}):{" "}
            {MOTIVO_LABELS[resultado.motivo] ?? "Motivo no documentado por el backend."}
          </p>
        </div>
      )}

      {resultado.status === "error" && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>No se pudo contactar a suit-orquestador para generar el checkout_token.</p>
        </div>
      )}

      {resultado.status === "ok" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="h-[640px] overflow-hidden rounded-lg border border-border">
            <iframe
              src={`${ORQUESTADOR_PUBLIC_URL}/api/autorizacion/cobro/formulario/?checkout_token=${encodeURIComponent(resultado.checkoutToken)}`}
              title="Formulario de cobro BDV Pago Móvil C2P"
              className="h-full w-full"
            />
          </div>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Datos de prueba (BDV QA)</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              <div>
                <p className="text-muted-foreground">Banco (único disponible)</p>
                <p className="font-medium text-foreground">Banco de Venezuela</p>
              </div>
              <div>
                <p className="text-muted-foreground">Cédula</p>
                <p className="font-medium text-foreground">V12345678</p>
              </div>
              <div>
                <p className="text-muted-foreground">Teléfono</p>
                <p className="font-medium text-foreground">04125692243</p>
              </div>
              <div>
                <p className="text-muted-foreground">Código OTP</p>
                <p className="font-medium text-foreground">5551111</p>
              </div>
              <p className="text-xs text-muted-foreground">
                Valores exactos documentados en el PDF dummy de BDV QA — cualquier otro dato no
                funciona contra el ambiente de pruebas. En este ambiente Calidad, BDV no envía SMS
                real: el OTP siempre es el valor fijo de arriba.
              </p>
              <p className="text-xs text-muted-foreground">
                Quirk conocido del ambiente QA, no un bug: al confirmar el cobro con el OTP, este
                dummy específico de BDV <strong>siempre</strong> va a responder con el código{" "}
                <code>1001</code> no documentado. El dummy exige match literal contra{" "}
                <code>&quot;1000.6&quot;</code> del PDF, pero el <code>DecimalField(19,2)</code>{" "}
                de producción del Orquestador cuantiza cualquier monto a 2 decimales
                (<code>&quot;1000.60&quot;</code>) sin excepción — evitarlo exigiría romper el
                formato real de producción solo para esta pantalla de prueba, y es una decisión
                explícita no construir ese override. No es un bug de este Portal ni del
                Orquestador.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
