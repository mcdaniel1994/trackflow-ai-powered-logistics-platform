import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createInboundOrder,
  createOutboundOrder,
  listMovements,
  listProducts,
  parseInventoryError,
} from "@/lib/inventory/api";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

describe("inventory API client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("builds bounded pagination queries", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response('{"items":[],"total":0,"limit":10,"offset":30}', {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listProducts(10, 30);
    await listMovements(10, 20);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/inventory/products?limit=10&offset=30");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/inventory/orders?limit=10&offset=20");
  });

  it("sends only writable movement fields and adds CSRF through the shared auth client", async () => {
    document.cookie = "trackflow_csrf=csrf-token";
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response('{"id":1}', { status: 201, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createInboundOrder({ sku_id: 3, quantity: 4, reference: "PO-4", warehouse: "LA" });
    await createOutboundOrder({ sku_id: 3, quantity: 2, exit_type: "loss", tracking_number: null, warehouse: "LA" });

    const inbound = fetchMock.mock.calls[0][1] as RequestInit;
    const outbound = fetchMock.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(inbound.body))).toEqual({ sku_id: 3, quantity: 4, reference: "PO-4", warehouse: "LA" });
    expect(JSON.parse(String(outbound.body))).toEqual({ sku_id: 3, quantity: 2, exit_type: "loss", tracking_number: null, warehouse: "LA" });
    expect((inbound.headers as Headers).get(CSRF_HEADER_NAME)).toBe("csrf-token");
    expect(String(inbound.body)).not.toContain("current_stock");
    expect(String(inbound.body)).not.toContain("user_uuid");
  });

  it("parses string and validation failures without exposing malformed bodies", async () => {
    await expect(parseInventoryError(new Response('{"detail":"Insufficient stock"}', { status: 400 }))).resolves.toMatchObject({
      status: 400,
      message: "Insufficient stock",
    });
    await expect(parseInventoryError(new Response('{"detail":[{"loc":["body","quantity"],"msg":"Input should be greater than 0"}]}', { status: 422 }))).resolves.toMatchObject({
      status: 422,
      fieldErrors: { quantity: "Input should be greater than 0" },
    });
    await expect(parseInventoryError(new Response("<html>upstream secret</html>", { status: 503 }))).resolves.toMatchObject({
      status: 503,
      message: "Inventory service is temporarily unavailable.",
    });
  });
});
