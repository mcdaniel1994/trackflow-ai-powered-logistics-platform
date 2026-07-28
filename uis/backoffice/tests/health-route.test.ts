// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/health/route";
import { GET as live } from "@/app/api/health/live/route";
import { GET as reporting } from "@/app/api/health/reporting/route";

describe("deployment health route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("aggregates Identity and Central API readiness", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await GET();
    expect(response.status).toBe(200);
    expect(response.status).not.toBe(307);
    expect(await response.json()).toEqual({ status: "ready" });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8002/health",
      "http://localhost:8003/health/ready",
    ]);
  });

  it("returns one generic failure without exposing dependency details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private service URL and secret")));
    const response = await GET();
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ status: "not_ready" });
  });

  it("keeps process liveness independent of all dependencies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("dependencies unavailable")));
    const response = await live();
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "alive" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("proxies reporting verification without promoting it to readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({ status: "degraded", queue_state: "unavailable" }, { status: 503 }),
      ),
    );
    const response = await reporting();
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({
      status: "degraded",
      queue_state: "unavailable",
    });
  });
});
