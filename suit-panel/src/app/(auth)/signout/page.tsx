"use client";

import { useEffect } from "react";
import { signOut } from "next-auth/react";

export default function Page() {
  useEffect(() => {
    void signOut({ callbackUrl: "/login" });
  }, []);

  return <p className="text-sm text-muted-foreground">Cerrando sesion...</p>;
}
