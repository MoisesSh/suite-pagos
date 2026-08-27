import Link from "next/link";
import { BookOpen, FilePlus2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-10 px-4 py-16">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Developer Portal de la Suite de Pagos
        </h1>
        <p className="max-w-xl text-base text-muted-foreground">
          Punto de entrada para equipos externos que integran la pasarela de pagos: registro de
          aplicaciones y dominios autorizados, y documentación de las APIs disponibles.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <BookOpen className="size-5 text-muted-foreground" aria-hidden="true" />
            <CardTitle>Documentación</CardTitle>
            <CardDescription>
              Explora el contrato OpenAPI disponible hoy (suit-conciliacion).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              className="w-full"
              render={<Link href="/documentacion" />}
            >
              Ver documentación
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <FilePlus2 className="size-5 text-muted-foreground" aria-hidden="true" />
            <CardTitle>Registrar aplicación</CardTitle>
            <CardDescription>
              Solicita autorización de dominio y proveedor de pago para tu app.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" render={<Link href="/aplicaciones/nueva" />}>
              Nueva solicitud
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
