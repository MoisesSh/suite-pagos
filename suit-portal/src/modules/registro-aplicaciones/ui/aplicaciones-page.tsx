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

      <AplicacionForm />
    </div>
  );
}
