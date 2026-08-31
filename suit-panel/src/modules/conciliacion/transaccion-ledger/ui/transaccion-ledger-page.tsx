import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { fetchTransaccionLedgerAction } from "../infrastructure/actions/transaccion-ledger-actions";

interface TransaccionLedgerPageProps {
  id: string;
}

export default async function TransaccionLedgerPage({ id }: TransaccionLedgerPageProps) {
  const transaccion = await fetchTransaccionLedgerAction(id);
  if (!transaccion) notFound();

  return (
    <div className="flex flex-col gap-6 px-6 py-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Transaccion de ledger</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">{transaccion.id}</p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-2 text-sm">
          <div className="flex justify-between text-muted-foreground">
            <span>Evento de referencia</span>
            <span className="text-foreground">{transaccion.referenciaEvento}</span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Creada</span>
            <span className="text-foreground">{new Date(transaccion.createdAt).toLocaleString()}</span>
          </div>
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-2 text-sm font-medium text-foreground">Lineas ({transaccion.lineas.length})</h2>
        <div className="flex flex-col gap-2">
          {transaccion.lineas.map((linea) => (
            <Card key={linea.id}>
              <CardContent className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <Badge variant={linea.tipo === "debito" ? "secondary" : "default"}>{linea.tipo}</Badge>
                  <span className="text-xs text-muted-foreground">{linea.cuenta}</span>
                </div>
                <span className="font-medium text-foreground">{linea.monto}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
