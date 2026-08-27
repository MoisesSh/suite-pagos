---
name: patrones-implementacion-frontend
description: Patrones de implementacion en Next.js con react-hook-form + zod, componentes UI compartidos, loading states, permisos, reportes PDF, tema oscuro/claro y revalidacion.
---

# Patrones de Implementacion Frontend

Skill con los patrones concretos de implementacion para construir features sobre la arquitectura SCREAM-Feature-Onion.

**Los componentes de `components/ui/` son shadcn/ui** (código copiado al repo, no una librería en `node_modules`). Antes de asumir que un componente existe o de escribir uno a mano, verifica si ya está instalado (`ls components/ui/`); si falta, instálalo con `npx shadcn@latest add <nombre>` en vez de crearlo desde cero. Cuando el setup del proyecto lo requiera completo, instala todos los componentes disponibles con `npx shadcn@latest add --all`.

---

## Form building

### Flujo completo

```
1. Zod schema               ui/schema/schema-[nombre].ts
2. Form component           ui/[nombre]-form.tsx  ("use client")
     useForm<T>({ resolver: zodResolver(schema), defaultValues })
     useTransition() → startTransition
3. Server action            infrastructure/actions/[nombres]-actions.ts  ("use server")
4. Use case                  application/use-cases/[accion].ts
5. Repository port           domain/ports/repo-[nombre].ts
6. Repository impl           infrastructure/repositories/repo-[nombre]-api.ts
7. HTTP functions            infrastructure/http/[nombres]-api.ts
8. apiClient                 shared/infrastructure/http/fetcher-api.ts
```

### Ejemplos completos por tipo

#### 1. Create form — InputForm + SelectForm basico

```typescript
// modules/[modulo]/ui/schema/schema-[nombre].ts
import { z } from "zod";

export const [nombre]FormSchema = z.object({
  nombre: z.string().min(2, "Minimo 2 caracteres"),
  descripcion: z.string().min(4, "Minimo 4 caracteres"),
  tipo: z.string().min(1, "Seleccione un tipo"),
});

export type [Nombre]FormType = z.infer<typeof [nombre]FormSchema>;
```

```typescript
// modules/[modulo]/ui/[nombre]-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/components/card";
import { Plus, Spinner, FileText, Tag } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";
import { create[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";

export default function [Nombre]Form({ onSuccess }: { onSuccess?: () => void }) {
  const [isPending, startTransition] = useTransition();

  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: { nombre: "", descripcion: "", tipo: "" },
  });

  const onSubmit = (data: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await create[Nombre]Action(data);
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      form.reset();
      onSuccess?.();
    });
  };

  const tipoOptions = [
    { value: "tipo1", label: "Tipo 1" },
    { value: "tipo2", label: "Tipo 2" },
    { value: "tipo3", label: "Tipo 3" },
  ];

  return (
    <Card>
      <CardHeader><CardTitle>Nuevo [Nombre]</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <InputForm<[Nombre]FormType>
            form={form}
            name="nombre"
            title="Nombre"
            type="text"
            placeholder="Ej. nombre del [nombre]"
            subTitle="Nombre descriptivo"
            icon={Tag}
          />
          <InputForm<[Nombre]FormType>
            form={form}
            name="descripcion"
            title="Descripcion"
            type="text"
            placeholder="Ej. descripcion detallada"
            subTitle="Breve descripcion"
            icon={FileText}
          />
          <SelectForm<[Nombre]FormType, { value: string; label: string }>
            form={form}
            name="tipo"
            title="Tipo"
            type="select"
            placeholder="Seleccione un tipo"
            subTitle="Categoria del [nombre]"
            options={tipoOptions}
            valueKey="value"
            labelKey="label"
          />
          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? <Spinner className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {isPending ? "Creando..." : "Crear [Nombre]"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

#### 2. Edit form — defaultValues desde DTO

```typescript
// modules/[modulo]/ui/[nombre]-edit-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/components/card";
import { Plus, Spinner, FloppyDisk, User, Tag } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";
import { update[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";
import type { [Nombre]ItemDTO } from "../application/dtos/[nombre]-dto";

interface [Nombre]EditFormProps {
  item: [Nombre]ItemDTO;
  tipoOptions: { value: string; label: string }[];
}

export default function [Nombre]EditForm({ item, tipoOptions }: [Nombre]EditFormProps) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: {
      nombre: item.nombre,
      descripcion: item.descripcion,
      tipo: item.tipo,
    },
  });

  const onSubmit = (data: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await update[Nombre]Action(item.id, data);
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      router.back();
    });
  };

  return (
    <Card>
      <CardHeader><CardTitle>Editar [Nombre]</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <InputForm<[Nombre]FormType>
            form={form} name="nombre" title="Nombre" type="text" icon={Tag}
          />
          <InputForm<[Nombre]FormType>
            form={form} name="descripcion" title="Descripcion" type="text" icon={User}
          />
          <SelectForm<[Nombre]FormType, { value: string; label: string }>
            form={form} name="tipo" title="Tipo" type="select"
            options={tipoOptions} valueKey="value" labelKey="label"
          />
          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? <Spinner className="size-4 animate-spin" /> : <FloppyDisk className="size-4" />}
            {isPending ? "Guardando..." : "Guardar Cambios"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

#### 3. Form con FileForm — subida de archivos multipart

```typescript
// modules/[modulo]/ui/schema/schema-[nombre].ts
import { z } from "zod";

export const [nombre]FormSchema = z.object({
  descripcion: z.string().min(4, "Minimo 4 caracteres"),
  tipo: z.enum(["Opcion 1", "Opcion 2", "Opcion 3"]),
  archivo: z.instanceof(File).optional(),
});

export type [Nombre]FormType = z.infer<typeof [nombre]FormSchema>;
```

```typescript
// modules/[modulo]/ui/[nombre]-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import FileForm from "@/shared/ui/components/file-form";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/components/card";
import { Plus, Spinner, FileText, Image, ForkKnife } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";
import { create[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";

export default function [Nombre]Form({ onSuccess }: { onSuccess?: () => void }) {
  const [isPending, startTransition] = useTransition();
  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: { descripcion: "", tipo: "Opcion 1" },
  });

  const onSubmit = (data: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await create[Nombre]Action({
        descripcion: data.descripcion,
        tipo: data.tipo,
        archivo: data.archivo ?? null,
      });
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      form.reset();
      onSuccess?.();
    });
  };

  const opciones = [
    { value: "Opcion 1", label: "Opcion 1" },
    { value: "Opcion 2", label: "Opcion 2" },
    { value: "Opcion 3", label: "Opcion 3" },
  ];

  return (
    <Card>
      <CardHeader><CardTitle>Nuevo [Nombre]</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <SelectForm<[Nombre]FormType, { value: string; label: string }>
            form={form} name="tipo" title="Tipo" type="select"
            placeholder="Seleccione" options={opciones}
            valueKey="value" labelKey="label" icon={ForkKnife}
          />
          <InputForm<[Nombre]FormType>
            form={form} name="descripcion" title="Descripcion" type="text"
            placeholder="Ej. descripcion" icon={FileText}
          />
          <FileForm<[Nombre]FormType>
            form={form} name="archivo" title="Archivo"
            accept="image/*" subTitle="Sube una imagen (opcional)" icon={Image}
          />
          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? <Spinner className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {isPending ? "Creando..." : "Crear [Nombre]"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

#### 4. Form con cascading selects — options desde SWR

```typescript
// modules/[modulo]/ui/[nombre]-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { toast } from "sonner";
import useSWR from "swr";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/components/card";
import { Plus, Spinner, User, Flag, MapPin } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";
import { create[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";
import { fetch[Recurso1]Action, fetch[Recurso2]Action } from "../infrastructure/actions/[nombres]-actions";

export default function [Nombre]Form({ onSuccess }: { onSuccess?: () => void }) {
  const [isPending, startTransition] = useTransition();
  const { data: items1 } = useSWR("[recurso1]-opts", fetch[Recurso1]Action);
  const { data: items2 } = useSWR("[recurso2]-opts", fetch[Recurso2]Action);

  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: { campo_texto: "", id_recurso1: "", id_recurso2: "" },
  });

  const opciones1 = (items1 ?? []).map((i: { id: number; nombre: string }) => ({ value: String(i.id), label: i.nombre }));
  const opciones2 = (items2 ?? []).map((i: { id: number; nombre: string }) => ({ value: String(i.id), label: i.nombre }));

  const onSubmit = (d: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await create[Nombre]Action({
        campo_texto: d.campo_texto,
        id_recurso1: Number(d.id_recurso1),
        id_recurso2: Number(d.id_recurso2),
      });
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      form.reset();
      onSuccess?.();
    });
  };

  return (
    <Card>
      <CardHeader><CardTitle>Nuevo [Nombre]</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <InputForm<[Nombre]FormType>
            form={form} name="campo_texto" title="Campo Texto" type="text" icon={User}
          />
          <SelectForm<[Nombre]FormType, { value: string; label: string }>
            form={form} name="id_recurso1" title="[Recurso 1]" type="select"
            placeholder="Seleccione" options={opciones1}
            valueKey="value" labelKey="label" icon={Flag}
          />
          <SelectForm<[Nombre]FormType, { value: string; label: string }>
            form={form} name="id_recurso2" title="[Recurso 2]" type="select"
            placeholder="Seleccione" options={opciones2}
            valueKey="value" labelKey="label" icon={MapPin}
          />
          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? <Spinner className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {isPending ? "Creando..." : "Crear [Nombre]"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

#### 5. Form con CedulaSearch — busqueda de empleados

```typescript
// modules/[modulo]/ui/schema/schema-[nombre].ts
import { z } from "zod";

export const [nombre]FormSchema = z.object({
  id_[recurso]: z.number().min(1, "Debe buscar un [recurso]"),
  id_opcion: z.string().min(1, "Seleccione una opcion"),
});

export type [Nombre]FormType = z.infer<typeof [nombre]FormSchema>;
```

```typescript
// modules/[modulo]/ui/[nombre]-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import SelectForm from "@/shared/ui/components/select-form";
import CedulaSearch from "@/shared/ui/components/cedula-search";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/components/card";
import { Spinner, Link } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";
import { create[Nombre]Action } from "../infrastructure/actions/[nombres]-actions";

interface [Nombre]FormProps {
  opciones: { value: string; label: string }[];
}

export default function [Nombre]Form({ opciones }: [Nombre]FormProps) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: { id_[recurso]: 0, id_opcion: "" },
  });

  const onSubmit = (data: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await create[Nombre]Action(data);
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      router.push("/[ruta]");
    });
  };

  return (
    <Card>
      <CardHeader><CardTitle>Asignar [Nombre]</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <CedulaSearch
            onFound={(data) => {
              if (data.id) form.setValue("id_[recurso]", data.id);
            }}
            required
          />
          <SelectForm<[Nombre]FormType, { value: string; label: string }>
            form={form} name="id_opcion" title="Opcion" type="select"
            placeholder="Seleccione" options={opciones}
            valueKey="value" labelKey="label" icon={Link}
          />
          <Button type="submit" size="lg" disabled={isPending} className="w-full">
            {isPending ? <Spinner className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {isPending ? "Asignando..." : "Asignar"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

#### 6. Login form — 2 campos + manejo de errores

```typescript
// modules/sesion/ui/schema/schema-login.ts
import { z } from "zod";

export const signInSchema = z.object({
  usuario: z.string().min(1, "El usuario es requerido"),
  password: z.string().min(1, "La contrasena es requerida"),
});

export type loginType = z.infer<typeof signInSchema>;
```

```typescript
// modules/sesion/ui/login-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import { Button } from "@/shared/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/ui/components/card";
import { User, Key, SignIn, Spinner } from "@phosphor-icons/react";
import { loginType, signInSchema } from "./schema/schema-login";
import { loginAction } from "../infrastructure/actions/sesion-actions";

export function LoginForm() {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const form = useForm<loginType>({
    resolver: zodResolver(signInSchema),
    defaultValues: { usuario: "", password: "" },
  });

  const onSubmit = (data: loginType) => {
    startTransition(async () => {
      const result = await loginAction(data);
      if (result.error) { toast.error(result.error); return; }
      toast.success("Bienvenido al sistema");
      router.push("/");
    });
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="items-center pb-4 text-center">
        <CardTitle>Iniciar Sesion</CardTitle>
        <CardDescription>Ingrese sus credenciales</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-5">
          <InputForm<loginType>
            form={form} name="usuario" title="Usuario" type="text"
            placeholder="Ej. 12345678" subTitle="Ingrese su identificacion" icon={User}
          />
          <InputForm<loginType>
            form={form} name="password" title="Contrasena" type="password"
            placeholder="••••••••" subTitle="Ingrese su contrasena" icon={Key}
          />
          <Button type="submit" size="lg" disabled={isPending} className="mt-2 w-full">
            {isPending ? <Spinner className="size-4 animate-spin" /> : <SignIn className="size-4" />}
            {isPending ? "Ingresando..." : "Ingresar al Sistema"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

#### 7. Form con DateForm + DireccionAdminSelects — filtros

```typescript
// modules/[modulo]/ui/schema/schema-[nombre].ts
import { z } from "zod";

export const [nombre]FormSchema = z.object({
  fecha_inicio: z.string().optional(),
  fecha_fin: z.string().optional(),
  tipo: z.string().optional(),
});

export type [Nombre]FormType = z.infer<typeof [nombre]FormSchema>;
```

```typescript
// modules/[modulo]/ui/[nombre]-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import InputForm from "@/shared/ui/components/input-form";
import SelectForm from "@/shared/ui/components/select-form";
import DateForm from "@/shared/ui/components/date-form";
import DireccionAdminSelects from "@/shared/ui/components/direccion-admin-selects";
import { User } from "@phosphor-icons/react";
import { [Nombre]FormType, [nombre]FormSchema } from "./schema/schema-[nombre]";

export function [Nombre]FilterForm() {
  const form = useForm<[Nombre]FormType>({
    resolver: zodResolver([nombre]FormSchema),
    defaultValues: { fecha_inicio: "", fecha_fin: "", tipo: "", niveles: "", oficina: "", division: "", coordinacion: "" },
  });

  const tipoOptions = [
    { value: "opt1", label: "Opcion 1" },
    { value: "opt2", label: "Opcion 2" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4">
        <DateForm<[Nombre]FormType> form={form} name="fecha_inicio" title="Fecha Inicio" placeholder="Seleccione" />
        <DateForm<[Nombre]FormType> form={form} name="fecha_fin" title="Fecha Fin" placeholder="Seleccione" />
      </div>
      <SelectForm<[Nombre]FormType, { value: string; label: string }>
        form={form} name="tipo" title="Tipo" type="select"
        placeholder="Todos" options={tipoOptions} valueKey="value" labelKey="label"
      />
      <InputForm<[Nombre]FormType>
        form={form} name="cedula" title="Cedula" type="text" placeholder="Filtrar por cedula" icon={User}
      />
      <DireccionAdminSelects<[Nombre]FormType>
        form={form} nivelesName="niveles" oficinaName="oficina"
        divisionName="division" coordinacionName="coordinacion"
      />
    </div>
  );
}
```

### Reglas del patron

- Los forms usan `useTransition` para estados de carga (no useState + useEffect).
- `toast.success`/`toast.error` de `sonner` para feedback.
- `form.reset()` despues de crear exitosamente.
- `mutate()` de SWR para refrescar listas despues de una operacion.
- Los valores de selects vienen como `string` aunque el backend espere `number` — convertir en la server action.
- Schemas con `z.enum()` para selects con opciones fijas, `z.instanceof(File)` para uploads.

---

## Shared UI components — ejemplos de codigo

### Patron: Form field wrapper

Todos los form fields siguen el mismo patron: `Controller` de react-hook-form + sistema `Field` de shadcn.

```
Field(data-invalid)
├── FieldLabel
├── [Input | Select | Textarea | etc.]
├── FieldDescription (subTitle)
└── FieldError (errores validacion)
```

### InputForm

```typescript
// shared/ui/components/input-form.tsx
import { Controller, FieldValues, Path, UseFormReturn } from "react-hook-form";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { Input } from "./input";
import { ElementType } from "react";

interface InputForm<T extends FieldValues> {
  form: UseFormReturn<T>;
  title: string;
  placeholder?: string;
  subTitle?: string;
  name: Path<T>;
  type: string;
  className?: string;
  icon?: ElementType;
}

export default function InputForm<T extends FieldValues>(useForm: InputForm<T>) {
  return (
    <Controller
      name={useForm.name}
      control={useForm.form.control}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={field.name}>{useForm.title}</FieldLabel>
          <div className="relative flex items-center">
            {useForm.icon && (
              <useForm.icon
                className="absolute left-3 h-5 w-5 text-muted-foreground pointer-events-none"
                aria-hidden="true"
              />
            )}
            <Input
              {...field}
              id={field.name}
              type={useForm.type}
              aria-invalid={fieldState.invalid}
              placeholder={useForm.placeholder ?? ""}
              autoComplete="off"
              className={`${useForm.icon ? "pl-10" : ""} w-full`}
            />
          </div>
          <FieldDescription>{useForm.subTitle}</FieldDescription>
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  );
}
```

### SelectForm

```typescript
// shared/ui/components/select-form.tsx
import { Controller, FieldValues, Path, UseFormReturn } from "react-hook-form";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { ElementType } from "react";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "./select";

interface SelectForm<T extends FieldValues, D> {
  form: UseFormReturn<T>;
  title: string;
  placeholder?: string;
  subTitle?: string;
  name: Path<T>;
  type: string;
  options: D[];
  valueKey: keyof D;
  labelKey: keyof D;
  className?: string;
  icon?: ElementType;
}

export default function SelectForm<T extends FieldValues, D>(useForm: SelectForm<T, D>) {
  return (
    <Controller
      name={useForm.name}
      control={useForm.form.control}
      render={({ field, fieldState }) => {
        const selectedLabel = field.value
          ? String(useForm.options.find((o) => String(o[useForm.valueKey]) === field.value)?.[useForm.labelKey] ?? "")
          : "";

        return (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor={field.name}>{useForm.title}</FieldLabel>
            <div className="relative flex items-center">
              {useForm.icon && (
                <useForm.icon className="absolute left-3 h-5 w-5 text-muted-foreground pointer-events-none" />
              )}
              <Select name={useForm.name} value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id={field.name} aria-invalid={fieldState.invalid}
                  className={`${useForm.icon ? "pl-10" : ""} w-full text-foreground`}>
                  <SelectValue placeholder={useForm.placeholder ?? ""}>{selectedLabel}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {useForm.options.map((item, index) => (
                      <SelectItem key={index} value={String(item[useForm.valueKey])}>
                        {String(item[useForm.labelKey])}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <FieldDescription>{useForm.subTitle}</FieldDescription>
            {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
          </Field>
        );
      }}
    />
  );
}
```

### DateForm

```typescript
// shared/ui/components/date-form.tsx
"use client";
import { Controller, type FieldValues, type Path, type UseFormReturn } from "react-hook-form";
import { format, parse } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon } from "@phosphor-icons/react";
import type { ElementType } from "react";
import { Button } from "./button";
import { Calendar } from "./calendar";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { cn } from "@/lib/utils";

interface DateFormProps<T extends FieldValues> {
  form: UseFormReturn<T>;
  name: Path<T>;
  title: string;
  placeholder?: string;
  subTitle?: string;
  className?: string;
  icon?: ElementType;
}

const DATE_FORMAT = "yyyy-MM-dd";
const DISPLAY_FORMAT = "dd/MM/yyyy";

function parseDate(value: string): Date | undefined {
  const parsed = parse(value, DATE_FORMAT, new Date());
  return isNaN(parsed.getTime()) ? undefined : parsed;
}

export default function DateForm<T extends FieldValues>({ form, name, title, placeholder = "Seleccione una fecha",
  subTitle, className, icon: Icon }: DateFormProps<T>) {
  return (
    <Controller
      name={name}
      control={form.control}
      render={({ field, fieldState }) => {
        const selectedDate = field.value ? parseDate(field.value) : undefined;
        return (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor={field.name}>{title}</FieldLabel>
            <Popover>
              <PopoverTrigger id={field.name} aria-invalid={fieldState.invalid} data-slot="popover-trigger"
                render={
                  <Button variant="outline"
                    className={cn("w-full justify-start text-left font-normal", !field.value && "text-muted-foreground", Icon && "pl-10", className)}>
                    {Icon && <Icon className="absolute left-3 h-5 w-5 text-muted-foreground pointer-events-none" />}
                    <CalendarIcon className="size-4 text-muted-foreground" />
                    {field.value ? format(parseDate(field.value)!, DISPLAY_FORMAT, { locale: es }) : <span>{placeholder}</span>}
                  </Button>
                } />
              <PopoverContent className="w-auto p-0">
                <Calendar mode="single" selected={selectedDate}
                  onSelect={(date: Date | undefined) => field.onChange(date ? format(date, DATE_FORMAT) : "")}
                  locale={es} />
              </PopoverContent>
            </Popover>
            <FieldDescription>{subTitle}</FieldDescription>
            {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
          </Field>
        );
      }}
    />
  );
}
```

### FileForm

```typescript
// shared/ui/components/file-form.tsx
import { Controller, FieldValues, Path, UseFormReturn } from "react-hook-form";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { Input } from "./input";
import { ElementType } from "react";

interface FileForm<T extends FieldValues> {
  form: UseFormReturn<T>;
  title: string;
  subTitle?: string;
  name: Path<T>;
  accept?: string;
  className?: string;
  icon?: ElementType;
}

export default function FileForm<T extends FieldValues>(props: FileForm<T>) {
  return (
    <Controller
      name={props.name}
      control={props.form.control}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel>{props.title}</FieldLabel>
          <div className="relative flex items-center">
            {props.icon && (
              <props.icon className="absolute left-3 h-5 w-5 text-muted-foreground pointer-events-none" />
            )}
            <Input type="file" accept={props.accept}
              onChange={(e) => field.onChange(e.target.files?.[0] ?? null)}
              className={`${props.icon ? "pl-10" : ""} w-full`}
              ref={field.ref} name={field.name} onBlur={field.onBlur} />
          </div>
          {props.subTitle && <FieldDescription>{props.subTitle}</FieldDescription>}
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  );
}
```

### TextareaForm

```typescript
// shared/ui/components/textarea-form.tsx
import { Controller, FieldValues, Path, UseFormReturn } from "react-hook-form";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { Textarea } from "./textarea";

interface TextareaFormProps<T extends FieldValues> {
  form: UseFormReturn<T>;
  title: string;
  placeholder?: string;
  subTitle?: string;
  name: Path<T>;
  className?: string;
}

export default function TextareaForm<T extends FieldValues>(props: TextareaFormProps<T>) {
  return (
    <Controller
      name={props.name}
      control={props.form.control}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={field.name}>{props.title}</FieldLabel>
          <Textarea {...field} id={field.name} aria-invalid={fieldState.invalid}
            placeholder={props.placeholder ?? ""} className="min-h-24" />
          <FieldDescription>{props.subTitle}</FieldDescription>
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  );
}
```

---

### Componentes complejos

### DireccionAdminSelects — 4 selects en cascada

```typescript
// shared/ui/components/direccion-admin-selects.tsx
"use client";
import useSWR from "swr";
import { useEffect } from "react";
import { type FieldValues, type Path, type UseFormReturn } from "react-hook-form";
import SelectForm from "./select-form";
import { fetchDependenciasAction, fetchDireccionesGeneralesAction,
  fetchDireccionesLineaAction, fetchCoordinacionesAction } from "@/shared/infrastructure/actions/direcciones-actions";
import { Building, GitBranch, StackSimple } from "@phosphor-icons/react";

interface DireccionAdminSelectsProps<T extends FieldValues> {
  form: UseFormReturn<T>;
  nivelesName: Path<T>;
  oficinaName: Path<T>;
  divisionName: Path<T>;
  coordinacionName: Path<T>;
}

export default function DireccionAdminSelects<T extends FieldValues>({
  form, nivelesName, oficinaName, divisionName, coordinacionName,
}: DireccionAdminSelectsProps<T>) {
  const { data: dependencias } = useSWR("dependencias", fetchDependenciasAction);
  const { data: direccionesGenerales } = useSWR("direcciones-generales", fetchDireccionesGeneralesAction);
  const { data: direccionesLinea } = useSWR("direcciones-linea", fetchDireccionesLineaAction);
  const { data: coordinaciones } = useSWR("coordinaciones", fetchCoordinacionesAction);

  const selectedNiveles = form.watch(nivelesName);
  const selectedOficina = form.watch(oficinaName);
  const selectedDivision = form.watch(divisionName);

  const opcionesNiveles = (dependencias ?? []).map((d) => ({ value: String(d.id), label: d.dependencia }));
  const opcionesOficinas = (direccionesGenerales ?? [])
    .filter((dg) => String(dg.dependencia_id) === selectedNiveles)
    .map((dg) => ({ value: String(dg.id), label: dg.direccion_general }));
  const opcionesDivisiones = (direccionesLinea ?? [])
    .filter((dl) => String(dl.direccion_general_id) === selectedOficina)
    .map((dl) => ({ value: String(dl.id), label: dl.direccion_linea }));
  const opcionesCoordinaciones = (coordinaciones ?? [])
    .filter((c) => String(c.direccion_linea_id) === selectedDivision)
    .map((c) => ({ value: String(c.id), label: c.coordinacion }));

  // Reseteo en cascada
  useEffect(() => { form.resetField(oficinaName); form.resetField(divisionName); form.resetField(coordinacionName); }, [selectedNiveles]);
  useEffect(() => { form.resetField(divisionName); form.resetField(coordinacionName); }, [selectedOficina]);
  useEffect(() => { form.resetField(coordinacionName); }, [selectedDivision]);

  return (
    <div className="grid grid-cols-2 gap-4">
      <SelectForm<T, { value: string; label: string }> form={form} name={nivelesName} title="Nivel"
        type="select" placeholder="Seleccione un nivel" options={opcionesNiveles}
        valueKey="value" labelKey="label" icon={StackSimple} />
      <SelectForm<T, { value: string; label: string }> form={form} name={oficinaName} title="Oficina / Gerencia"
        type="select" placeholder={selectedNiveles ? "Seleccione una oficina" : "Primero seleccione un nivel"}
        options={opcionesOficinas} valueKey="value" labelKey="label" icon={Building} />
      <SelectForm<T, { value: string; label: string }> form={form} name={divisionName} title="Division"
        type="select" placeholder={selectedOficina ? "Seleccione una division" : "Primero seleccione una oficina"}
        options={opcionesDivisiones} valueKey="value" labelKey="label" icon={GitBranch} />
      <SelectForm<T, { value: string; label: string }> form={form} name={coordinacionName} title="Coordinacion"
        type="select" placeholder={selectedDivision ? "Seleccione una coordinacion" : "Primero seleccione una division"}
        options={opcionesCoordinaciones} valueKey="value" labelKey="label" icon={Building} />
    </div>
  );
}
```

### CedulaSearch — busqueda de empleados por cedula

```typescript
// shared/ui/components/cedula-search.tsx
"use client";
import { useState, useTransition } from "react";
import { CheckCircle, XCircle, MagnifyingGlass, Spinner } from "@phosphor-icons/react";
import { validateCedulaAction } from "@/shared/infrastructure/actions/empleados-actions";

interface CedulaSearchProps {
  onFound?: (data: { id?: number; cedula: string; nombres: string; apellidos: string }) => void;
  placeholder?: string;
  label?: string;
  required?: boolean;
}

export default function CedulaSearch({ onFound, placeholder = "Ej. 12345678", label = "Cedula", required = false }: CedulaSearchProps) {
  const [cedula, setCedula] = useState("");
  const [result, setResult] = useState<{ found: boolean; nombres?: string; apellidos?: string; id?: number } | null>(null);
  const [isPending, startTransition] = useTransition();

  const handleValidate = () => {
    if (!cedula || cedula.length < 6) return;
    startTransition(async () => {
      const r = await validateCedulaAction(cedula);
      setResult(r);
      if (r.found && onFound) onFound({ id: r.id, cedula: r.cedulaIdentidad, nombres: r.nombres ?? "", apellidos: r.apellidos ?? "" });
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <div className="flex gap-2">
        <input type="text" value={cedula} onChange={(e) => { setCedula(e.target.value); setResult(null); }}
          placeholder={placeholder}
          className="flex-1 rounded-lg border border-input bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-ring/20 outline-none transition-all"
          required={required} />
        <button type="button" onClick={handleValidate} disabled={isPending || cedula.length < 6}
          className="px-3 py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5">
          {isPending ? <Spinner className="size-4 animate-spin" /> : <MagnifyingGlass className="size-4" />}
          Validar
        </button>
      </div>
      {result && (
        <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${result.found ? "bg-success/10 text-success border border-success/20" : "bg-destructive/10 text-destructive border border-destructive/20"}`}>
          {result.found ? (
            <><CheckCircle className="size-4" /><span>{result.nombres} {result.apellidos}</span></>
          ) : (
            <><XCircle className="size-4" /><span>Cedula no encontrada en talento humano</span></>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## Layout components

### PageLayout

```typescript
// shared/ui/layout/page-layout.tsx
import type { LayoutPropsInterface } from "@/shared/types/layout-props";

export default function PageLayout(props: LayoutPropsInterface) {
  return (
    <div className="px-6 py-4 flex flex-col gap-6">
      {props.title && (
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">{props.title}</h1>
          {props.subTitle && <p className="text-sm text-muted-foreground mt-0.5">{props.subTitle}</p>}
        </div>
      )}
      <main>{props.children}</main>
    </div>
  );
}
```

### HeaderLayout

```typescript
// shared/ui/layout/header-layout.tsx
interface HeaderLayoutProps {
  children?: React.ReactNode;     // left (sidebar trigger)
  title?: string;
  subTitle?: string;
  right?: React.ReactNode;        // right (user avatar, logout)
}

export default function HeaderLayout({ children, title, subTitle, right }: HeaderLayoutProps) {
  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-border bg-background/80 backdrop-blur-sm px-4">
      <div className="flex items-center gap-2">{children}</div>
      <div className="flex items-center gap-1">
        {title && <span className="text-sm font-medium text-foreground">{title}</span>}
      </div>
      <div className="flex items-center gap-2">{right}</div>
    </header>
  );
}
```

### ReporteFiltrosDialog + ReporteBoton

```typescript
// shared/ui/components/reporte-filtros-dialog.tsx
// Dialog con filtros: fechas, cedula, tipo_comida/tipo_transporte, DireccionAdminSelects
// → queryParams(params) → fetch("/api/reportes/pdf/?" + qs)
// → createDownloadUrl(blob) → descarga automatica

// shared/ui/components/reporte-boton.tsx
// Boton "Reporte" que abre el ReporteFiltrosDialog
// Recibe: servicioId, servicioTipo ("comedor" | "transporte")
```

---

## Loading States

El proyecto usa 5 patrones distintos para estados de carga.

### a. useTransition — Boton con Spinner (forms)

```typescript
"use client";
import { useTransition } from "react";
import { Spinner, Plus } from "@phosphor-icons/react";
import { Button } from "@/shared/ui/components/button";

export default function [Nombre]Form() {
  const [isPending, startTransition] = useTransition();

  const onSubmit = (data: [Nombre]FormType) => {
    startTransition(async () => {
      const r = await create[Nombre]Action(data);
      if (r.error) { toast.error(r.error); return; }
      toast.success(r.success);
      form.reset();
    });
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Button type="submit" disabled={isPending}>
        {isPending ? <Spinner className="size-4 animate-spin" /> : <Plus className="size-4" />}
        {isPending ? "Creando..." : "Crear"}
      </Button>
    </form>
  );
}
```

### b. SWR isLoading — Spinner central (listas)

```typescript
const { data: items, isLoading, mutate } = useSWR("[nombres]", fetch[Nombres]Action);

{isLoading ? (
  <div className="flex justify-center py-6">
    <Spinner className="size-6 animate-spin text-muted-foreground" />
  </div>
) : !items?.length ? (
  <p className="text-center text-muted-foreground py-6">No hay [nombres] registrados.</p>
) : (
  items.map((item) => (
    <Card key={item.id}>...</Card>
  ))
)}
```

### c. Skeleton — placeholder de carga

```typescript
// shared/ui/components/skeleton.tsx
export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props} />
  );
}

// Uso:
<div className="space-y-3">
  <Skeleton className="h-4 w-[250px]" />
  <Skeleton className="h-4 w-[200px]" />
  <Skeleton className="h-4 w-[150px]" />
</div>
```

### d. Loading page — app router

```typescript
// app/(app)/loading.tsx
"use client";
export default function Loading() {
  // Animacion personalizada visible al navegar entre rutas
  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-8">
      <div className="relative size-28">
        {/* Cuadrados rotando con animacion */}
      </div>
      <p className="text-sm font-medium text-muted-foreground">Cargando</p>
    </div>
  );
}
```

### e. EmptyState — sin datos

```typescript
// shared/ui/components/empty.tsx
import { Tray } from "@phosphor-icons/react";
import { Button } from "./button";

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ title = "Sin datos", description = "No hay informacion disponible.", action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted">
        <Tray className="size-6 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="text-xs text-muted-foreground max-w-[280px]">{description}</p>
      {action && <Button variant="outline" size="sm" onClick={action.onClick}>{action.label}</Button>}
    </div>
  );
}

// Uso:
import { EmptyState } from "@/shared/ui/components/empty";
{!items?.length && <EmptyState title="Sin vehiculos" description="No hay vehiculos registrados." />}
```

---

## Permisos / Control de acceso

Los permisos vienen de la sesion de next-auth en `session.user.permisos` como `{ id, code, name }[] | null`.

### Leer permisos

**En Server Component (layouts):**

```typescript
import { auth } from "@/auth";

const session = await auth();
const userPermisos = session?.user?.permisos ?? [];
```

**En Client Component (via useSession):**

```typescript
"use client";
import { useSession } from "next-auth/react";

function Componente() {
  const { data: session } = useSession();
  const userPermisos = session?.user?.permisos ?? [];
}
```

### Render condicional

Mostrar/ocultar elementos segun permisos:

```typescript
{userPermisos.some(p => p.code === "manage_vehiculos") && (
  <Link href="/vehiculos/crear">Nuevo Vehiculo</Link>
)}
```

### Mostrar permisos de un usuario (ejemplo real)

```typescript
// modules/usuarios/ui/usuarios-page.tsx
{u.permisos?.length ? (
  <div className="flex gap-1 flex-wrap">
    {u.permisos.map((p) => (
      <span key={p.id} className="text-xs px-2 py-0.5 rounded-full bg-secondary text-secondary-foreground">
        {p.name}
      </span>
    ))}
  </div>
) : (
  <span className="text-xs text-muted-foreground">Sin permisos</span>
)}
```

### Asignar permisos a un usuario (toggle buttons)

```typescript
"use client";
import useSWR from "swr";
import { loadPermisosAction } from "../infrastructure/actions/permisos-actions";

const { data: permisosData } = useSWR("permisos-catalog", loadPermisosAction);
const catalogo = permisosData ?? [];

// En el form:
const togglePermiso = (code: string) => {
  const current = form.getValues("permisos") ?? [];
  const updated = current.includes(code)
    ? current.filter((c: string) => c !== code)
    : [...current, code];
  form.setValue("permisos", updated);
};

// En el JSX:
{catalogo.map((p) => {
  const selected = (form.watch("permisos") ?? []).includes(p.code);
  return (
    <button key={p.id} type="button" onClick={() => togglePermiso(p.code)}
      className={`px-3 py-1.5 rounded-lg text-sm ${selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
      {p.name}
    </button>
  );
})}
```

---

## RevalidatePath

Usar `revalidatePath` cuando una Server Action modifica datos y la pagina que los muestra es un **Server Component** (no usa `"use client"` + SWR).

```typescript
"use server";

import { revalidatePath } from "next/cache";
import { repo[Nombre]Api } from "../repositories/repo-[nombre]-api";
import { update[Nombre] } from "../../application/use-cases/update-[nombre]";
import { handleSessionExpired } from "@/shared/infrastructure/http/errors";

export async function toggle[Nombre]Action(id: number, activo: boolean) {
  try {
    await update[Nombre](repo[Nombre]Api, id, { activo });
    revalidatePath("/[ruta]");                          // refresca server components
    return { success: activo ? "Activado" : "Desactivado" };
  } catch (error) {
    handleSessionExpired(error);
    return { error: "Error al cambiar estado" };
  }
}
```

**Regla:** `revalidatePath` refresca la cache de Server Components. Si la pagina es `"use client"` con SWR, usar `mutate()` en su lugar.

---

## Tema oscuro/claro

El proyecto usa `next-themes` + variables CSS. El `Toaster` de sonner lo integra automaticamente:

```typescript
// shared/ui/components/sonner.tsx
"use client";
import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();
  return <Sonner theme={theme as ToasterProps["theme"]} ... />;
};
```

Los componentes shadcn/ui ya tienen variantes `dark:` en sus estilos. El tema se controla con la clase `.dark` en `<html>`.

### ThemeToggle (ejemplo)

```typescript
"use client";
import { useTheme } from "next-themes";
import { Sun, Moon } from "@phosphor-icons/react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent">
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}
```

---

## Reportes PDF

Flujo completo para generar y descargar PDFs desde Django:

```
ReporteBoton (cliente)
  → abre ReporteFiltrosDialog
    → form con filtros (fechas, cedula, tipo, selects organizacionales)
    → queryParams(params)
    → fetch("/api/reportes/pdf/?" + qs)
      → API Route (app/api/reportes/pdf/route.ts)
        → lee dj_access de cookie
        → fetch(DJANGO_API_SERVER + "reportes/pdf/?..." + query)   proxy a Django
        → retorna Blob
    → createDownloadUrl(blob)     descarga el PDF
    → revokeDownloadUrl(url)      limpia al cerrar
```

### API Route — proxy PDF

```typescript
// app/api/reportes/pdf/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { cookies } = await import("next/headers");
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("dj_access")?.value;

  if (!accessToken) {
    return NextResponse.json({ detail: "No autenticado" }, { status: 401 });
  }

  const searchParams = request.nextUrl.searchParams.toString();
  const djangoUrl = `${process.env.DJANGO_API_SERVER}reportes/pdf/?${searchParams}`;

  const res = await fetch(djangoUrl, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!res.ok) {
    return NextResponse.json(
      { detail: `Error del servidor: ${res.status}` },
      { status: res.status },
    );
  }

  return new NextResponse(res.body, {
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/pdf",
      "Content-Disposition":
        res.headers.get("Content-Disposition") ?? "attachment; filename=reporte.pdf",
    },
  });
}
```

### Cliente — filtros + descarga

```typescript
// shared/ui/components/reporte-filtros-dialog.tsx (resumen)
const params: Record<string, string | number | boolean | undefined | null> = {
  servicio: servicioId,
  cedula: data.cedula,
  fecha_inicio: data.fecha_inicio,
  fecha_fin: data.fecha_fin,
  niveles: data.niveles,
  oficina: data.oficina,
  // ...
};
const qs = queryParams(params);

setIsPending(true);
try {
  const res = await fetch(`/api/reportes/pdf/${qs}`);
  const blob = await res.blob();
  const url = createDownloadUrl(blob);
  setDownloadUrl(url); // se descarga automaticamente via <a ref>
} catch (error) {
  toast.error("Error al generar el reporte");
} finally {
  setIsPending(false);
}
```

### Blob utils

```typescript
// shared/infrastructure/http/blob-utils.ts
export function createDownloadUrl(blob: Blob): string {
  return URL.createObjectURL(blob);
}

export function revokeDownloadUrl(url: string): void {
  URL.revokeObjectURL(url);
}
```
