"use server";

import { cookies } from "next/headers";
import { signOut } from "@/auth";
import { API } from "@/shared/commons/api";
import { REFRESH_COOKIE_NAME } from "@/auth.config";

export async function logoutAction(): Promise<void> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_COOKIE_NAME)?.value;

  if (refreshToken) {
    await fetch(`${API.conciliacionUrl}/api/auth/logout/`, {
      method: "POST",
      headers: { Cookie: `${REFRESH_COOKIE_NAME}=${refreshToken}` },
    }).catch(() => {});
  }
  cookieStore.delete(REFRESH_COOKIE_NAME);
  await signOut({ redirectTo: "/login" });
}
