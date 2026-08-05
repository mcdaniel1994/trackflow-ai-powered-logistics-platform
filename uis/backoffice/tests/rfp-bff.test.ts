// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/rfp/[[...path]]/route";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("RFP BFF", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.CENTRAL_API_URL;
  });

  it("routes allowlisted ticket reads to Central API with filters and cookies", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", { headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://backoffice.test/api/rfp/tickets?status=analyzing", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context(["tickets"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/rfp/tickets?status=analyzing");
    expect((fetchMock.mock.calls[0][1].headers as Headers).get("Cookie")).toContain("trackflow_access=access");
  });

  it("routes a ticket detail read", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const id = "0a1b2c3d";

    await GET(new NextRequest(`http://backoffice.test/api/rfp/tickets/${id}`), context(["tickets", id]));

    expect(fetchMock.mock.calls[0][0].toString()).toBe(`http://central.test/rfp/tickets/${id}`);
  });

  it("forwards CSRF on the upload POST", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"id":"x"}', { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const headers = {
      Cookie: "trackflow_access=access; trackflow_csrf=csrf",
      "Content-Type": "multipart/form-data; boundary=abc",
      [CSRF_HEADER_NAME]: "csrf",
    };

    await POST(
      new NextRequest("http://backoffice.test/api/rfp/tickets", { method: "POST", body: "--abc--", headers }),
      context(["tickets"]),
    );

    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/rfp/tickets");
    expect((fetchMock.mock.calls[0][1].headers as Headers).get(CSRF_HEADER_NAME)).toBe("csrf");
  });

  it("does not expose mutating verbs beyond POST", async () => {
    const route = await import("@/app/api/rfp/[[...path]]/route");
    expect("PATCH" in route).toBe(false);
    expect("PUT" in route).toBe(false);
    expect("DELETE" in route).toBe(false);
  });

  it.each([
    ["GET", ["analyze"]],
    ["GET", ["tickets", "zzz"]],
    ["GET", ["tickets", "0a1b", "extra"]],
    ["POST", ["tickets", "0a1b"]],
  ])("blocks non-allowlisted %s routes", async (method, path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(`http://backoffice.test/api/rfp/${path.join("/")}`, { method });
    const response = method === "GET" ? await GET(request, context(path)) : await POST(request, context(path));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns a safe upstream failure without leaking details", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection secret")));

    const response = await GET(new NextRequest("http://backoffice.test/api/rfp/tickets"), context(["tickets"]));

    expect(response.status).toBe(503);
    expect(JSON.stringify(await response.json())).not.toContain("secret");
  });
});
