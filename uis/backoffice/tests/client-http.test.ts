import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchWithAuth } from "@/lib/auth/client-http";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

describe("fetchWithAuth", () => {
  beforeEach(() => {
    document.cookie = "trackflow_csrf=csrf-token";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches CSRF to state-changing same-origin requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchWithAuth("/api/suppliers", {
      method: "POST",
      body: JSON.stringify({ name: "Supplier" }),
    });

    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf-token");
    expect(fetchMock.mock.calls[0][1]?.credentials).toBe("include");
  });

  it("refreshes once on 401 and retries the original request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }))
      .mockResolvedValueOnce(new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchWithAuth("/api/users");

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/refresh");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/users");
  });

  it("emits a session-expired event when refresh fails", async () => {
    const listener = vi.fn();
    window.addEventListener("trackflow:auth-session-expired", listener);

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchWithAuth("/api/users", { redirectOnUnauthorized: false });

    expect(response.status).toBe(401);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("trackflow:auth-session-expired", listener);
  });
});
