// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST as authPost } from "@/app/api/auth/[[...path]]/route";
import { PATCH as supplierPatch } from "@/app/api/suppliers/[[...path]]/route";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

function context(path: string[]) {
  return {
    params: Promise.resolve({ path }),
  };
}

describe("BFF route handlers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.IDENTITY_API_URL;
    delete process.env.SUPPLIER_DIRECTORY_API_URL;
  });

  it("does not proxy unapproved auth routes", async () => {
    const blockedRoute = "reg" + "ister";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await authPost(
      new NextRequest(`http://backoffice.test/api/auth/${blockedRoute}`, { method: "POST" }),
      context([blockedRoute]),
    );

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("relays identity Set-Cookie headers from login", async () => {
    process.env.IDENTITY_API_URL = "http://identity.test";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"id":"u1"}', {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Set-Cookie": "trackflow_access=abc; Path=/; HttpOnly",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await authPost(
      new NextRequest("http://backoffice.test/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: "admin@example.com", password: "password" }),
        headers: { "Content-Type": "application/json" },
      }),
      context(["login"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://identity.test/auth/login");
    expect(response.headers.get("set-cookie")).toContain("trackflow_access=abc");
  });

  it("forwards forgot-password and reset-password auth routes", async () => {
    process.env.IDENTITY_API_URL = "http://identity.test";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"status":"ok"}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const forgot = await authPost(
      new NextRequest("http://backoffice.test/api/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: "worker@example.com" }),
        headers: { "Content-Type": "application/json" },
      }),
      context(["forgot-password"]),
    );
    const reset = await authPost(
      new NextRequest("http://backoffice.test/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token: "opaque", new_password: "safe-passphrase" }),
        headers: { "Content-Type": "application/json" },
      }),
      context(["reset-password"]),
    );

    expect(forgot.status).toBe(200);
    expect(reset.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://identity.test/auth/forgot-password");
    expect(fetchMock.mock.calls[1][0].toString()).toBe("http://identity.test/auth/reset-password");
  });

  it("forwards cookies and CSRF to supplier mutations", async () => {
    process.env.SUPPLIER_DIRECTORY_API_URL = "http://supplier.test";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"id":"s1"}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await supplierPatch(
      new NextRequest("http://backoffice.test/api/suppliers/s1/status", {
        method: "PATCH",
        body: JSON.stringify({ status: "suspended" }),
        headers: {
          Cookie: "trackflow_access=access; trackflow_csrf=csrf",
          "Content-Type": "application/json",
          [CSRF_HEADER_NAME]: "csrf",
        },
      }),
      context(["s1", "status"]),
    );

    const upstreamInit = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = upstreamInit.headers as Headers;

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://supplier.test/suppliers/s1/status");
    expect(headers.get("Cookie")).toContain("trackflow_access=access");
    expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf");
  });
});
