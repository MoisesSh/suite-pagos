import { TriangleAlert } from "lucide-react";
import AplicacionForm from "./aplicacion-form";

export default function AplicacionesPage() {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Registrar aplicación
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Solicitud de autorización de aplicación, dominio y proveedor de pago.
        </p>
      </div>

      <div
        role="status"
        className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
      >
        <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>
          Este formulario todavía <strong>no está conectado a ningún backend real</strong>. El
          CRUD de registro de aplicaciones/dominios/proveedores no existe hoy en
          suit-orquestador (solo se gestiona por Django admin). El envío se simula localmente
          para poder construir y validar la experiencia mientras ese endpoint se implementa.
        </p>
      </div>

      <AplicacionForm />
    </div>
  );
}
