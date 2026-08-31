import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface User {
    accessToken: string;
    username: string;
    isStaff: boolean;
    isSuperuser: boolean;
  }

  interface Session {
    accessToken: string;
    error?: "RefreshAccessTokenError";
    user: {
      id: string;
      username: string;
      isStaff: boolean;
      isSuperuser: boolean;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken: string;
    accessTokenExpires: number;
    id: string;
    username: string;
    isStaff: boolean;
    isSuperuser: boolean;
    error?: "RefreshAccessTokenError";
  }
}
