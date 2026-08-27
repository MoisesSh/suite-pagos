import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import { cookies } from "next/headers";
import authConfig, { REFRESH_COOKIE_NAME } from "./auth.config";
import { API } from "@/shared/commons/api";
import { decodeJwtExpiry } from "@/shared/infrastructure/http/jwt";
import { extractSetCookieValue } from "@/shared/infrastructure/http/parse-set-cookie";

async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const cookieStore = await cookies();
    const refreshToken = cookieStore.get(REFRESH_COOKIE_NAME)?.value;
    if (!refreshToken) throw new Error("No hay refresh_token disponible");

    const res = await fetch(`${API.conciliacionUrl}/api/auth/refresh/`, {
      method: "POST",
      headers: { Cookie: `${REFRESH_COOKIE_NAME}=${refreshToken}` },
    });
    if (!res.ok) throw new Error("El backend rechazo el refresh");

    const data = (await res.json()) as { access: string };
    const newRefreshToken = extractSetCookieValue(res, REFRESH_COOKIE_NAME);
    if (newRefreshToken) {
      cookieStore.set(REFRESH_COOKIE_NAME, newRefreshToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
      });
    }

    return {
      ...token,
      accessToken: data.access,
      accessTokenExpires: decodeJwtExpiry(data.access),
      error: undefined,
    };
  } catch {
    return { ...token, error: "RefreshAccessTokenError" };
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.accessTokenExpires = decodeJwtExpiry(user.accessToken);
        token.id = user.id as string;
        token.username = user.username;
        token.isStaff = user.isStaff;
        token.isSuperuser = user.isSuperuser;
        return token;
      }
      if (Date.now() < token.accessTokenExpires) return token;
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.error = token.error;
      session.user.id = token.id;
      session.user.username = token.username;
      session.user.isStaff = token.isStaff;
      session.user.isSuperuser = token.isSuperuser;
      return session;
    },
  },
});
