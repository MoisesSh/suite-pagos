"use client";

import { useTransition } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  activarAplicacionAction,
  fetchAplicacionesAction,
} from "../infrastructure/actions/aplicaciones-actions";
import AplicacionForm from "./aplicacion-form";
import type { AplicacionItemDTO } from "../application/dtos/aplicacion-dto";

function ToggleActivaButton({ aplicacion, onDone }: { aplicacion: AplicacionItemDTO; onDone: () => void }) {
  const [isPending, startTransition] = useTransition();

  const onClick = () => {
    startTransition(async () => {
      const r = await activarAplicacionAction(aplicacion.id, !aplicacion.activa);
      if (r.error) {
        toast.error(r.error);
        return;
      }
      toast.success(r.success);
      onDone();
    });
  };

  return (
    <Button variant="outline" size="sm" disabled={isPending} onClick={onClick}>
      {isPending ? "..." : aplicacion.activa ? "Desactivar" : "Activar"}
    </Button>
  );
}

export default function AplicacionesPage() {
  const { data: aplicaciones, isLoading, mutate } = useSWR("aplicaciones", fetchAplicacionesAction);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Aplicaciones</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Registro de apps consumidoras, dominios y proveedores autorizados en suit-orquestador.
        </p>
      </div>

      <AplicacionForm onCreated={() => mutate()} />

      <div>
        <h2 className="mb-2 text-sm font-medium text-foreground">
          Registradas {aplicaciones ? `(${aplicaciones.length})` : ""}
        </h2>

        {isLoading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : !aplicaciones?.length ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No hay aplicaciones registradas todavia.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {aplicaciones.map((aplicacion) => (
              <Card key={aplicacion.id}>
                <CardContent className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{aplicacion.nombre}</span>
                      <Badge variant={aplicacion.activa ? "default" : "outline"}>
                        {aplicacion.activa ? "activa" : "inactiva"}
                      </Badge>
                    </div>
                    <ToggleActivaButton aplicacion={aplicacion} onDone={() => mutate()} />
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {aplicacion.dominios.map((d) => (
                      <Badge key={d.id} variant="outline">
                        {d.dominio}
                      </Badge>
                    ))}
                    {aplicacion.proveedoresAutorizados.map((p) => (
                      <Badge key={p.id} variant="secondary">
                        {p.proveedor}
                      </Badge>
                    ))}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Creada: {new Date(aplicacion.createdAt).toLocaleString()}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
