"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchEventosAction } from "../infrastructure/actions/eventos-actions";

export default function EventosPage() {
  const [search, setSearch] = useState("");
  const { data: eventos, isLoading } = useSWR(["eventos", search], () => fetchEventosAction(search));

  return (
    <div className="flex flex-col gap-6 px-6 py-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Eventos</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Eventos de pago recibidos por conciliacion.
        </p>
      </div>

      <Input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Buscar por event_id o event_type"
        className="max-w-sm"
      />

      {isLoading ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : !eventos?.length ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No hay eventos registrados.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {eventos.map((evento) => (
            <Card key={evento.id}>
              <CardContent className="flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-foreground">{evento.eventType}</p>
                  <p className="text-xs text-muted-foreground">{evento.eventId}</p>
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <p>v{evento.schemaVersion}</p>
                  <p>
                    {evento.procesadoAt
                      ? `Procesado: ${new Date(evento.procesadoAt).toLocaleString()}`
                      : "Sin procesar"}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
