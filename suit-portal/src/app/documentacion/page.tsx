import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { CONCILIACION_DOCS_URL, ORQUESTADOR_PUBLIC_URL } from "@/shared/commons/api";

export const metadata = {
  title: "Documentación — Developer Portal",
};

export default function DocumentacionPage() {
  const orquestadorDocsUrl = `${ORQUESTADOR_PUBLIC_URL}/api/docs/`;

  return (
    <div className="flex w-full flex-1 flex-col gap-4 px-4 py-6">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Documentación de API</h1>
        <p className="text-sm text-muted-foreground">
          Swagger UI de{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-foreground">suit-conciliacion</code>,
          embebido abajo.{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-foreground">suit-orquestador</code>{" "}
          (autorización de cobro) expone el suyo en{" "}
          <a
            href={orquestadorDocsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            su propio Swagger
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
          .
        </p>

        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-900"
        >
          <p>
            Si querés integrar el cobro embebido por iframe (el caso de uso más común para equipos
            externos), no necesitás leer estos schemas técnicos — seguí la{" "}
            <Link href="/guia" className="inline-flex items-center gap-1 font-medium underline">
              guía de integración
              <ArrowRight className="size-3" aria-hidden="true" />
            </Link>
            , pensada paso a paso para eso.
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
