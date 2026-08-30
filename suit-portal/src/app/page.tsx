import Link from "next/link";
import { ArrowRight, BookOpen, KeySquare, MessageSquareCode, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

const PASOS = [
  {
    icon: KeySquare,
    titulo: "Tu app queda registrada",
    detalle:
      "El equipo de Conatel registra tu dominio y proveedor de pago (hoy solo BDV) en el Orquestador.",
  },
  {
    icon: ShieldCheck,
    titulo: "Iniciás el checkout y embebés el iframe",
    detalle:
      "Tu servidor pide un checkout_token y tu página embebe el formulario real de cobro.",
  },
  {
    icon: MessageSquareCode,
    titulo: "Escuchás el resultado",
    detalle: "Un postMessage para la UX y un webhook firmado como fuente de verdad.",
  },
] as const;

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-10 px-4 py-16">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Developer Portal de la Suite de Pagos
        </h1>
        <p className="max-w-xl text-base text-muted-foreground">
          Documentación para equipos de apps consumidoras de Conatel (Conatel en Línea,
          Homologación, futuras) que quieren cobrar embebiendo el formulario de pago por iframe.
        </p>
      </div>

      <ol className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {PASOS.map((paso, i) => (
          <li key={paso.titulo} className="rounded-lg border border-border p-4">
            <div className="flex items-center gap-2">
              <paso.icon className="size-4 text-muted-foreground" aria-hidden="true" />
              <span className="text-xs font-medium text-muted-foreground">Paso {i + 1}</span>
            </div>
            <p className="mt-2 text-sm font-medium text-foreground">{paso.titulo}</p>
            <p className="mt-1 text-xs text-muted-foreground">{paso.detalle}</p>
          </li>
        ))}
      </ol>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Button size="lg" nativeButton={false} render={<Link href="/guia" />}>
          Ver guía de integración
          <ArrowRight className="size-4" aria-hidden="true" />
        </Button>
        <Button
          size="lg"
          variant="outline"
          nativeButton={false}
          render={<Link href="/documentacion" />}
        >
          <BookOpen className="size-4" aria-hidden="true" />
          Ver documentación OpenAPI
        </Button>
      </div>
    </div>
  );
}
