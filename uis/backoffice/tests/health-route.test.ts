// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/health/route";

describe("deployment health route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("aggregates Identity and Central API readiness", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await GET();
    expect(response.status).toBe(200);
    expect(response.status).not.toBe(307);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8002/health",
      "http://localhost:8003/health/ready",
    ]);
  });

  it("returns one generic failure without exposing dependency details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private service URL and secret")));
    const response = await GET();
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ status: "unavailable" });
  });
});
