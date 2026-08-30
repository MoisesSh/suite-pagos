import { ArrowRight } from "lucide-react";

export type FlowActor = "servidor" | "navegador" | "orquestador";

export interface FlowStep {
  de: FlowActor;
  a: FlowActor;
  texto: string;
}

const ACTOR_LABEL: Record<FlowActor, string> = {
  servidor: "Tu servidor",
  navegador: "Navegador del pagador",
  orquestador: "Orquestador",
};

const ACTOR_STYLE: Record<FlowActor, string> = {
  servidor: "border-blue-200 bg-blue-50 text-blue-700",
  navegador: "border-violet-200 bg-violet-50 text-violet-700",
  orquestador: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

function ActorBadge({ actor }: { actor: FlowActor }) {
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${ACTOR_STYLE[actor]}`}
    >
      {ACTOR_LABEL[actor]}
    </span>
  );
}

// Representación de un diagrama de secuencia como lista numerada (no un SVG
// de swimlanes): comunica el mismo flujo sin depender de una librería de
// diagramado ni de un layout que se rompa en mobile.
export default function FlowDiagram({ steps }: { steps: FlowStep[] }) {
  return (
    <ol className="flex flex-col gap-2">
      {steps.map((step, i) => (
        <li key={i} className="rounded-lg border border-border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">{i + 1}</span>
            <ActorBadge actor={step.de} />
            <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            <ActorBadge actor={step.a} />
          </div>
          <p className="mt-1.5 text-sm text-foreground">{step.texto}</p>
        </li>
      ))}
    </ol>
  );
}
