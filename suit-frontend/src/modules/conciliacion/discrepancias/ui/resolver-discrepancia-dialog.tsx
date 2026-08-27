"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import SelectForm from "@/shared/ui/components/select-form";
import TextareaForm from "@/shared/ui/components/textarea-form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { resolverDiscrepanciaAction } from "../infrastructure/actions/discrepancias-actions";
import {
  ResolverDiscrepanciaFormType,
  resolverDiscrepanciaFormSchema,
} from "./schema/schema-resolver-discrepancia";
import type { DiscrepanciaItemDTO } from "../application/dtos/discrepancia-dto";

const ESTADO_OPTIONS = [
  { value: "en_revision", label: "En revision" },
  { value: "resuelta", label: "Resuelta" },
  { value: "descartada", label: "Descartada" },
];

interface ResolverDiscrepanciaDialogProps {
  discrepancia: DiscrepanciaItemDTO;
  onResolved: () => void;
}

export default function ResolverDiscrepanciaDialog({
  discrepancia,
  onResolved,
}: ResolverDiscrepanciaDialogProps) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const form = useForm<ResolverDiscrepanciaFormType>({
    resolver: zodResolver(resolverDiscrepanciaFormSchema),
    defaultValues: {
      estadoResolucion:
        discrepancia.estadoResolucion === "pendiente" ? "en_revision" : discrepancia.estadoResolucion,
      notas: discrepancia.notas,
    },
  });

  const onSubmit = (data: ResolverDiscrepanciaFormType) => {
    startTransition(async () => {
      const result = await resolverDiscrepanciaAction(discrepancia.id, data);
      if ("error" in result) {
        toast.error(result.error);
        return;
      }
      toast.success(result.success);
      setOpen(false);
      onResolved();
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>Resolver</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Resolver discrepancia</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <SelectForm<ResolverDiscrepanciaFormType>
            form={form}
            name="estadoResolucion"
            title="Estado"
            placeholder="Seleccione un estado"
            options={ESTADO_OPTIONS}
          />
          <TextareaForm<ResolverDiscrepanciaFormType>
            form={form}
            name="notas"
            title="Notas"
            placeholder="Detalle de la resolucion"
          />
          <DialogFooter>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
