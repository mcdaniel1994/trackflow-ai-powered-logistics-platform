import { cookies } from "next/headers";
import { ACCESS_COOKIE_NAME } from "@/lib/auth/constants";
import type { AuthUser } from "@/lib/auth/types";

const DEFAULT_IDENTITY_API_URL = "http://localhost:8002";

export function getIdentityAPIURL() {
  return (process.env.IDENTITY_API_URL ?? DEFAULT_IDENTITY_API_URL).replace(/\/$/, "");
}

export async function getServerSessionUser(): Promise<AuthUser | null> {
  const cookieStore = await cookies();

  if (!cookieStore.has(ACCESS_COOKIE_NAME)) {
    return null;
  }

  try {
    const response = await fetch(`${getIdentityAPIURL()}/auth/me`, {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Cookie: cookieStore.toString(),
      },
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as AuthUser;
  } catch {
    // Fail closed for SSR auth gates if identity is unreachable or returns bad JSON.
    return null;
  }
}
