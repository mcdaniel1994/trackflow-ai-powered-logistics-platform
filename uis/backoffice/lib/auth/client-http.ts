import {
  AUTH_SESSION_EXPIRED_EVENT,
  CSRF_HEADER_NAME,
  STATE_CHANGING_METHODS,
} from "@/lib/auth/constants";
import { readCSRFCookie } from "@/lib/auth/csrf";
import { loginPathFor } from "@/lib/auth/redirects";

type AuthFetchOptions = RequestInit & {
  retryOnUnauthorized?: boolean;
  redirectOnUnauthorized?: boolean;
};

function isBrowser() {
  return typeof window !== "undefined";
}

function requestMethod(init?: RequestInit) {
  return (init?.method ?? "GET").toUpperCase();
}

export function authHeaders(init?: RequestInit) {
  const headers = new Headers(init?.headers);

  if (STATE_CHANGING_METHODS.has(requestMethod(init))) {
    const csrfToken = readCSRFCookie();
    if (csrfToken) {
      headers.set(CSRF_HEADER_NAME, csrfToken);
    }
  }

  return headers;
}

export function notifySessionExpired() {
  if (!isBrowser()) {
    return;
  }

  window.dispatchEvent(new CustomEvent(AUTH_SESSION_EXPIRED_EVENT));
}

function redirectToLogin() {
  if (!isBrowser()) {
    return;
  }

  const next = `${window.location.pathname}${window.location.search}`;
  window.location.assign(loginPathFor(next));
}

async function refreshSession() {
  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: authHeaders({ method: "POST" }),
  });

  return response.ok;
}

export async function fetchWithAuth(input: RequestInfo | URL, init: AuthFetchOptions = {}) {
  const { retryOnUnauthorized = true, redirectOnUnauthorized = true, ...requestInit } = init;
  const request = {
    ...requestInit,
    cache: requestInit.cache ?? "no-store",
    credentials: requestInit.credentials ?? "include",
    headers: authHeaders(requestInit),
  } satisfies RequestInit;

  let response = await fetch(input, request);

  if (response.status !== 401 || !retryOnUnauthorized || !isBrowser()) {
    return response;
  }

  if (await refreshSession()) {
    response = await fetch(input, {
      ...request,
      headers: authHeaders(requestInit),
    });
  }

  if (response.status === 401) {
    notifySessionExpired();
    if (redirectOnUnauthorized) {
      redirectToLogin();
    }
  }

  return response;
}
