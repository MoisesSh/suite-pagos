import { ExternalLink, TriangleAlert } from "lucide-react";
import { CONCILIACION_DOCS_URL } from "@/shared/commons/api";

export const metadata = {
  title: "Documentación — Developer Portal",
};

export default function DocumentacionPage() {
  return (
    <div className="flex w-full flex-1 flex-col gap-4 px-4 py-6">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Documentación de API</h1>
        <p className="text-sm text-muted-foreground">
          Swagger UI de{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-foreground">suit-conciliacion</code>,
          único backend con OpenAPI expuesto hoy.
        </p>

        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            <strong>suit-orquestador</strong> (autorización de cobro, registro de aplicaciones)
            todavía no expone documentación OpenAPI — no tiene <code>drf-spectacular</code>{" "}
            configurado. Solo se documenta aquí lo que ya existe en suit-conciliacion.
          </p>
        </div>

        <a
          href={CONCILIACION_DOCS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          Abrir en una pestaña nueva
          <ExternalLink className="size-3.5" aria-hidden="true" />
        </a>
      </div>

      <div className="mx-auto h-[70vh] w-full max-w-5xl overflow-hidden rounded-lg border border-border">
        <iframe
          src={CONCILIACION_DOCS_URL}
          title="Swagger UI — suit-conciliacion"
          className="h-full w-full"
        />
      </div>
    </div>
  );
}
