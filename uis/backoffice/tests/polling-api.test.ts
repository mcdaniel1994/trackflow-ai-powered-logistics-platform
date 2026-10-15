import { afterEach, describe, expect, it, vi } from "vitest";
import { getDispatchMetrics, getReceivingMetrics, getStockLossMetrics } from "@/lib/telemetry/api";
import { listMovements } from "@/lib/inventory/api";
const range = { from: "2026-10-01", to: "2026-10-07" };

afterEach(() => { vi.unstubAllGlobals(); });
describe("dashboard cancellation through authenticated fetch helpers", () => {
  it.each([getDispatchMetrics, getReceivingMetrics, getStockLossMetrics])("forwards the signal through initial fetch and 401 refresh retry", async (getMetrics) => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response("{}", { status: 401 })).mockResolvedValueOnce(new Response("{}", { status: 200 })).mockResolvedValueOnce(new Response('{"rows":[]}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    expect(await getMetrics(range, controller.signal)).toEqual({ rows: [] });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ signal: controller.signal, credentials: "include", cache: "no-store" });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/refresh");
    expect(fetchMock.mock.calls[2][1].signal).toBe(controller.signal);
  });
  it("forwards cancellation for movement reads and propagates abort without retrying", async () => {
    const controller = new AbortController();
    const error = new DOMException("Aborted", "AbortError");
    const fetchMock = vi.fn().mockRejectedValue(error);
    vi.stubGlobal("fetch", fetchMock);
    controller.abort();
    await expect(listMovements(8, 0, controller.signal)).rejects.toBe(error);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
  });
});
