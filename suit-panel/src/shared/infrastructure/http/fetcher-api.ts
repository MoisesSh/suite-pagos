import { auth } from "@/auth";
import { API } from "@/shared/commons/api";
import { SessionExpiredError } from "./errors";

async function authHeader(): Promise<Record<string, string>> {
  const session = await auth();
  if (!session?.accessToken || session.error) throw new SessionExpiredError();
  return { Authorization: `Bearer ${session.accessToken}` };
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) throw new SessionExpiredError();
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Error ${res.status} al consultar ${API.conciliacionUrl}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const apiClient = {
  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${API.conciliacionUrl}${path}`, {
      headers: await authHeader(),
      cache: "no-store",
    });
    return parseResponse<T>(res);
  },

  /** Como `get`, pero devuelve `null` en 404 en vez de lanzar. */
  async getOrNull<T>(path: string): Promise<T | null> {
    const res = await fetch(`${API.conciliacionUrl}${path}`, {
      headers: await authHeader(),
      cache: "no-store",
    });
    if (res.status === 404) return null;
    return parseResponse<T>(res);
  },

  async patch<T>(path: string, body?: object): Promise<T> {
    const res = await fetch(`${API.conciliacionUrl}${path}`, {
      method: "PATCH",
      headers: { ...(await authHeader()), "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    return parseResponse<T>(res);
  },
};
