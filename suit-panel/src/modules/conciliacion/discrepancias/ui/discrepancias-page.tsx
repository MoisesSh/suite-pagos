"use client";

import { useState } from "react";
import useSWR from "swr";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchDiscrepanciasAction } from "../infrastructure/actions/discrepancias-actions";
import ResolverDiscrepanciaDialog from "./resolver-discrepancia-dialog";
import type { EstadoResolucion } from "../domain/entities/discrepancia-entity";

const ESTADO_FILTRO_OPTIONS: { value: EstadoResolucion; label: string }[] = [
  { value: "abierta", label: "Abierta" },
  { value: "en_revision", label: "En revision" },
  { value: "resuelta", label: "Resuelta" },
  { value: "descartada", label: "Descartada" },
];

const SEVERIDAD_FILTRO_OPTIONS = ["baja", "media", "alta", "critica"];

const ESTADO_BADGE_VARIANT: Record<EstadoResolucion, "default" | "secondary" | "destructive" | "outline"> = {
  abierta: "outline",
  en_revision: "secondary",
  resuelta: "default",
  descartada: "destructive",
};

export default function DiscrepanciasPage() {
  const [estadoResolucion, setEstadoResolucion] = useState<EstadoResolucion | undefined>(undefined);
  const [severidad, setSeveridad] = useState<string | undefined>(undefined);

  const filtro = { estadoResolucion, severidad };
  const { data: discrepancias, isLoading, mutate } = useSWR(
    ["discrepancias", estadoResolucion, severidad],
    () => fetchDiscrepanciasAction(filtro),
  );

  return (
    <div className="flex flex-col gap-6 px-6 py-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Discrepancias</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Discrepancias detectadas por conciliacion entre movimientos, consultas y eventos.
        </p>
      </div>

      <div className="flex flex-wrap gap-4">
        <Select
          value={estadoResolucion ?? "todos"}
          onValueChange={(value) =>
            setEstadoResolucion(value === "todos" ? undefined : (value as EstadoResolucion))
          }
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="todos">Todos los estados</SelectItem>
              {ESTADO_FILTRO_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>

        <Select
          value={severidad ?? "todas"}
          onValueChange={(value) => setSeveridad(!value || value === "todas" ? undefined : value)}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Severidad" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="todas">Todas las severidades</SelectItem>
              {SEVERIDAD_FILTRO_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : !discrepancias?.length ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No hay discrepancias para los filtros seleccionados.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {discrepancias.map((discrepancia) => (
            <Card key={discrepancia.id}>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{discrepancia.tipo}</span>
                    <Badge variant="outline">{discrepancia.severidad}</Badge>
                    <Badge variant={ESTADO_BADGE_VARIANT[discrepancia.estadoResolucion]}>
                      {discrepancia.estadoResolucion}
                    </Badge>
                  </div>
                  <ResolverDiscrepanciaDialog discrepancia={discrepancia} onResolved={() => mutate()} />
                </div>
                {discrepancia.notas && (
                  <p className="text-sm text-muted-foreground">{discrepancia.notas}</p>
                )}
                <div className="flex flex-wrap gap-x-4 text-xs text-muted-foreground">
                  <span>Creada: {new Date(discrepancia.createdAt).toLocaleString()}</span>
                  {discrepancia.resueltoPor && (
                    <span>Resuelta por: {discrepancia.resueltoPor.username}</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
