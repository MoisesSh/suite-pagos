import TransaccionLedgerPage from "@/modules/conciliacion/transaccion-ledger/ui/transaccion-ledger-page";

export default async function Page({ params }: PageProps<"/transacciones-ledger/[id]">) {
  const { id } = await params;
  return <TransaccionLedgerPage id={id} />;
}
