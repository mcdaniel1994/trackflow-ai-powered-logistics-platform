// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, PATCH, POST } from "@/app/api/inventory/[[...path]]/route";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("inventory BFF", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.CENTRAL_API_URL;
  });

  it("allowlists reads and forwards query parameters and auth cookies", async () => {
    process.env.CENTRAL_API_URL = "http://central.test/";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"items":[],"total":0,"limit":20,"offset":20}', {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://backoffice.test/api/inventory/products?limit=20&offset=20", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context(["products"]),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/inventory/products?limit=20&offset=20");
    expect(headers.get("Cookie")).toContain("trackflow_access=access");
  });

  it("forwards CSRF for an allowlisted inventory write", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"id":1}', { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("http://backoffice.test/api/inventory/orders/inbound", {
        method: "POST",
        body: JSON.stringify({ sku_id: 1, quantity: 5, reference: "PO-1", warehouse: "LA" }),
        headers: {
          Cookie: "trackflow_access=access; trackflow_csrf=csrf",
          "Content-Type": "application/json",
          [CSRF_HEADER_NAME]: "csrf",
        },
      }),
      context(["orders", "inbound"]),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;

    expect(response.status).toBe(201);
    expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf");
  });

  it("allowlists client administration and threshold updates with validated identifiers", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"client_name":"Renamed"}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const clientId = "11111111-1111-4111-8111-111111111111";

    const response = await PATCH(
      new NextRequest(`http://backoffice.test/api/inventory/clients/${clientId}`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: "Renamed" }),
      }),
      context(["clients", clientId]),
    );
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe(`http://central.test/inventory/clients/${clientId}`);
  });

  it("preserves Central API authentication failures for shared refresh handling", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response('{"detail":"Not authenticated"}', {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ));

    const response = await GET(
      new NextRequest("http://backoffice.test/api/inventory/products", {
        headers: { Cookie: "trackflow_access=expired" },
      }),
      context(["products"]),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Not authenticated" });
  });

  it.each([
    ["PATCH", ["clients", "not-a-uuid"]],
    ["GET", ["products", "not-a-number"]],
    ["GET", ["orders", "outbound"]],
    ["POST", ["orders"]],
  ])("blocks non-allowlisted %s routes", async (method, path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(`http://backoffice.test/api/inventory/${path.join("/")}`, { method });
    const response = method === "GET" ? await GET(request, context(path)) : method === "PATCH" ? await PATCH(request, context(path)) : await POST(request, context(path));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [new Error("connection secret"), 503, "Service temporarily unavailable"],
    [Object.assign(new Error("timeout secret"), { name: "TimeoutError" }), 504, "Service timed out"],
  ])("returns safe dependency failures", async (failure, status, detail) => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure));

    const response = await GET(
      new NextRequest("http://backoffice.test/api/inventory/orders"),
      context(["orders"]),
    );
    const body = await response.json();

    expect(response.status).toBe(status);
    expect(body).toEqual({ detail });
    expect(JSON.stringify(body)).not.toContain("secret");
  });
});
