"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { toast } from "sonner";
import InputForm from "@/shared/ui/components/input-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoginFormType, loginFormSchema } from "./schema/schema-login";

export default function LoginForm() {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const form = useForm<LoginFormType>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = (data: LoginFormType) => {
    startTransition(async () => {
      const result = await signIn("credentials", { ...data, redirect: false });
      if (result?.error) {
        toast.error("Credenciales invalidas");
        return;
      }
      toast.success("Bienvenido");
      router.push("/discrepancias");
      router.refresh();
    });
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Iniciar sesion</CardTitle>
        <CardDescription>Panel de conciliacion — suit-conciliacion</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <InputForm<LoginFormType>
            form={form}
            name="email"
            title="Email"
            type="email"
            placeholder="usuario@ejemplo.com"
          />
          <InputForm<LoginFormType>
            form={form}
            name="password"
            title="Contrasena"
            type="password"
            placeholder="********"
          />
          <Button type="submit" size="lg" disabled={isPending} className="mt-2 w-full">
            {isPending ? "Ingresando..." : "Ingresar"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
