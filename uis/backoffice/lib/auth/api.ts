import { fetchWithAuth } from "@/lib/auth/client-http";
import { parseAPIError } from "@/lib/auth/errors";
import type { AuthUser, CreatedUser } from "@/lib/auth/types";

async function jsonRequest<T>(path: string, init?: RequestInit, retryOnUnauthorized = true): Promise<T> {
  const body = typeof init?.body === "string" ? init.body : undefined;
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetchWithAuth(
    path,
    {
      ...init,
      body,
      headers,
      retryOnUnauthorized,
    },
  );

  if (!response.ok) {
    throw await parseAPIError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function login(email: string, password: string) {
  return jsonRequest<AuthUser>(
    "/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    false,
  );
}

export async function getMe() {
  return jsonRequest<AuthUser>("/api/auth/me", undefined, false);
}

export async function logout() {
  await jsonRequest<{ status: string }>("/api/auth/logout", { method: "POST" }, false);
}

export async function changePassword(currentPassword: string, newPassword: string) {
  return jsonRequest<AuthUser>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export async function forgotPassword(email: string) {
  return jsonRequest<{ message: string }>(
    "/api/auth/forgot-password",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
    false,
  );
}

export async function resetPassword(token: string, newPassword: string) {
  return jsonRequest<{ status: string }>(
    "/api/auth/reset-password",
    {
      method: "POST",
      body: JSON.stringify({
        token,
        new_password: newPassword,
      }),
    },
    false,
  );
}

export async function updateProfile(userId: string, name: string) {
  return jsonRequest<AuthUser>(`/api/users/${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

export async function listUsers() {
  return jsonRequest<AuthUser[]>("/api/users");
}

export async function createUser(name: string, email: string) {
  return jsonRequest<CreatedUser>("/api/users", {
    method: "POST",
    body: JSON.stringify({ name, email }),
  });
}

export async function updateUserStatus(userId: string, status: AuthUser["status"]) {
  return jsonRequest<AuthUser>(`/api/users/${encodeURIComponent(userId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function revokeUserSessions(userId: string) {
  return jsonRequest<{ status: string }>(`/api/users/${encodeURIComponent(userId)}/sessions/revoke`, {
    method: "POST",
  });
}
