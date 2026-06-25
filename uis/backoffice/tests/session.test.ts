// @vitest-environment node

import { beforeEach, describe, expect, it, vi } from "vitest";
import { ACCESS_COOKIE_NAME } from "@/lib/auth/constants";

const sessionMocks = vi.hoisted(() => ({
  cookieStore: {
    has: vi.fn(),
    toString: vi.fn(),
  },
  cookies: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: sessionMocks.cookies,
}));

import { getServerSessionUser } from "@/lib/auth/session";

const user = {
  id: "user-1",
  name: "Admin User",
  email: "admin@example.com",
  role: "admin",
  status: "active",
  must_change_password: false,
  created_at: "2026-06-20T00:00:00Z",
  last_login_at: null,
};

describe("getServerSessionUser", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionMocks.cookies.mockResolvedValue(sessionMocks.cookieStore);
    sessionMocks.cookieStore.has.mockReturnValue(true);
    sessionMocks.cookieStore.toString.mockReturnValue(`${ACCESS_COOKIE_NAME}=access-token`);
    delete process.env.IDENTITY_API_URL;
  });

  it("returns null without an access-token cookie", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    sessionMocks.cookieStore.has.mockReturnValue(false);

    await expect(getServerSessionUser()).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns the current user from identity", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(user));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getServerSessionUser()).resolves.toEqual(user);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8002/auth/me",
      expect.objectContaining({
        method: "GET",
        cache: "no-store",
      }),
    );
  });

  it("returns null when identity rejects the session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Not authenticated" }, { status: 401 })));

    await expect(getServerSessionUser()).resolves.toBeNull();
  });

  it("fails closed when identity is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED access-token")));

    await expect(getServerSessionUser()).resolves.toBeNull();
  });

  it("fails closed when identity returns malformed JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not-json", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(getServerSessionUser()).resolves.toBeNull();
  });
});
