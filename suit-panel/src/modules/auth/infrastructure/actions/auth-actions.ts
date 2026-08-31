"use server";

import { cookies } from "next/headers";
import { auth, signOut } from "@/auth";
import { API } from "@/shared/commons/api";
import { REFRESH_COOKIE_NAME } from "@/auth.config";

export async function logoutAction(): Promise<void> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_COOKIE_NAME)?.value;
  const session = await auth();

  if (refreshToken && session?.accessToken) {
    await fetch(`${API.conciliacionUrl}/api/auth/logout/`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
        "Content-Type": "application/json",
        Cookie: `${REFRESH_COOKIE_NAME}=${refreshToken}`,
      },
      body: JSON.stringify({ refresh: refreshToken }),
    }).catch(() => {});
  }
  cookieStore.delete(REFRESH_COOKIE_NAME);
  await signOut({ redirectTo: "/login" });
}
