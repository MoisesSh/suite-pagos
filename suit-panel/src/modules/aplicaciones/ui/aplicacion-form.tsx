"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { createAplicacionAction } from "../infrastructure/actions/aplicaciones-actions";
import { AplicacionFormType, aplicacionFormSchema, PROVEEDOR_OPTIONS } from "./schema/schema-aplicacion";

const PROVEEDOR_SELECT_OPTIONS = PROVEEDOR_OPTIONS.map((p) => ({ value: p, label: p }));

export default function AplicacionForm({ onCreated }: { onCreated?: () => void }) {
  const [isPending, startTransition] = useTransition();

  const form = useForm<AplicacionFormType>({
    resolver: zodResolver(aplicacionFormSchema),
    defaultValues: { nombre: "", dominio: "", proveedor: undefined },
  });

  const onSubmit = (data: AplicacionFormType) => {
    startTransition(async () => {
      const r = await createAplicacionAction(data);
      if (r.error) {
        toast.error(r.error);
        return;
      }
      toast.success(r.success);
      form.reset();
      onCreated?.();
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Registrar aplicacion</CardTitle>
        <CardDescription>
          Autoriza una nueva app consumidora, su dominio y proveedor de pago en suit-orquestador.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <InputForm<AplicacionFormType>
            form={form}
            name="nombre"
            title="Nombre de la aplicacion"
            type="text"
            placeholder="Ej. Conatel en Linea"
            subTitle="Nombre legible de la app consumidora."
          />
          <InputForm<AplicacionFormType>
            form={form}
            name="dominio"
            title="Dominio autorizado"
            type="text"
            placeholder="conatel-en-linea.gob.ve"
            subTitle="Dominio exacto desde el que se embebe el formulario de cobro."
          />
          <SelectForm<AplicacionFormType>
            form={form}
            name="proveedor"
            title="Proveedor de pago"
            placeholder="Seleccione un proveedor"
            subTitle="Unico proveedor confirmado hoy (BDV Pago Movil C2P)."
            options={PROVEEDOR_SELECT_OPTIONS}
          />
          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? "Registrando..." : "Registrar aplicacion"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
