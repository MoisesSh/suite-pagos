import { redirect } from "next/navigation";
import { auth } from "@/auth";
import AplicacionesPage from "@/modules/aplicaciones/ui/aplicaciones-page";

export default async function Page() {
  const session = await auth();
  if (!session?.user.isStaff) redirect("/discrepancias");

  return <AplicacionesPage />;
}
