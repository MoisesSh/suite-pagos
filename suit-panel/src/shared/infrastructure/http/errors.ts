import { redirect } from "next/navigation";

export class SessionExpiredError extends Error {
  override readonly name = "SessionExpiredError";
}

export function handleSessionExpired(error: unknown): void {
  if (error instanceof SessionExpiredError) redirect("/signout");
}
