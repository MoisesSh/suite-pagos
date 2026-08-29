import type { NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { cookies } from "next/headers";
import { API } from "@/shared/commons/api";
import { extractSetCookieValue } from "@/shared/infrastructure/http/parse-set-cookie";

interface LoginResponse {
  access: string;
  usuario: {
    id: string;
    email: string;
    username: string;
    is_staff: boolean;
    is_superuser: boolean;
  };
}

export const REFRESH_COOKIE_NAME = "refresh_token";

export default {
  providers: [
    Credentials({
      credentials: { email: {}, password: {} },
      authorize: async (credentials) => {
        const email = credentials?.email;
        const password = credentials?.password;
        if (typeof email !== "string" || typeof password !== "string") return null;

        const res = await fetch(`${API.conciliacionUrl}/api/auth/login/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) return null;

        const data = (await res.json()) as LoginResponse;

        const refreshToken = extractSetCookieValue(res, REFRESH_COOKIE_NAME);
        if (!refreshToken) return null;
        const cookieStore = await cookies();
        cookieStore.set(REFRESH_COOKIE_NAME, refreshToken, {
          httpOnly: true,
          secure: process.env.NODE_ENV === "production",
          sameSite: "lax",
          path: "/",
        });

        return {
          id: data.usuario.id,
          email: data.usuario.email,
          username: data.usuario.username,
          isStaff: data.usuario.is_staff,
          isSuperuser: data.usuario.is_superuser,
          accessToken: data.access,
        };
      },
    }),
  ],
  pages: { signIn: "/login" },
} satisfies NextAuthConfig;
