"use client";

import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { toast } from "sonner";
import { Loader2, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { createAplicacionAction } from "../infrastructure/actions/aplicaciones-actions";
import {
  aplicacionFormSchema,
  PROVEEDOR_OPTIONS,
  type AplicacionFormType,
} from "./schema/schema-aplicacion";

export default function AplicacionForm() {
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
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Registrar aplicación</CardTitle>
        <CardDescription>
          Solicita autorización para que tu aplicación consuma la pasarela de pagos con un
          dominio y proveedor específicos.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Controller
              name="nombre"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor={field.name}>Nombre de la aplicación</FieldLabel>
                  <Input
                    {...field}
                    id={field.name}
                    aria-invalid={fieldState.invalid}
                    placeholder="Ej. Conatel en Línea"
                    autoComplete="off"
                  />
                  <FieldDescription>
                    Nombre legible de la app consumidora (equivalente a `AplicacionRegistrada.nombre`).
                  </FieldDescription>
                  {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
                </Field>
              )}
            />

            <Controller
              name="dominio"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor={field.name}>Dominio autorizado</FieldLabel>
                  <Input
                    {...field}
                    id={field.name}
                    aria-invalid={fieldState.invalid}
                    placeholder="conatel-en-linea.gob.ve"
                    autoComplete="off"
                  />
                  <FieldDescription>
                    Dominio exacto desde el que se embebe el formulario de cobro (equivalente a
                    `DominioPermitido.dominio`).
                  </FieldDescription>
                  {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
                </Field>
              )}
            />

            <Controller
              name="proveedor"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor={field.name}>Proveedor de pago</FieldLabel>
                  <Select
                    name={field.name}
                    value={field.value ?? ""}
                    onValueChange={field.onChange}
                  >
                    <SelectTrigger id={field.name} aria-invalid={fieldState.invalid}>
                      <SelectValue placeholder="Seleccione un proveedor" />
                    </SelectTrigger>
                    <SelectContent>
                      {PROVEEDOR_OPTIONS.map((proveedor) => (
                        <SelectItem key={proveedor} value={proveedor}>
                          {proveedor}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FieldDescription>
                    Único proveedor confirmado hoy en el plan de datos del Orquestador (BDV Pago
                    Móvil C2P).
                  </FieldDescription>
                  {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
                </Field>
              )}
            />

            <Button type="submit" size="lg" disabled={isPending} className="w-full">
              {isPending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              {isPending ? "Enviando..." : "Enviar solicitud"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
