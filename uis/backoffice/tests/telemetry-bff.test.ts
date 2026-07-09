// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import * as telemetryRoute from "@/app/api/telemetry/[[...path]]/route";

const { GET } = telemetryRoute;

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("telemetry BFF", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.CENTRAL_API_URL;
  });

  it("is read-only: exposes no write verbs", () => {
    expect("POST" in telemetryRoute).toBe(false);
    expect("PATCH" in telemetryRoute).toBe(false);
    expect("DELETE" in telemetryRoute).toBe(false);
  });

  it("allowlists a metrics read and forwards the range query and auth cookie", async () => {
    process.env.CENTRAL_API_URL = "http://central.test/";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"period":{"from":"2026-07-01","to":"2026-07-07"},"rows":[]}', {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://backoffice.test/api/telemetry/metrics/dispatch?from=2026-07-01&to=2026-07-07", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context(["metrics", "dispatch"]),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe(
      "http://central.test/telemetry/metrics/dispatch?from=2026-07-01&to=2026-07-07",
    );
    expect(headers.get("Cookie")).toContain("trackflow_access=access");
  });

  it("preserves Central API authentication failures for shared refresh handling", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"detail":"Not authenticated"}', {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const response = await GET(
      new NextRequest("http://backoffice.test/api/telemetry/metrics/dispatch?from=2026-07-01&to=2026-07-07", {
        headers: { Cookie: "trackflow_access=expired" },
      }),
      context(["metrics", "dispatch"]),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Not authenticated" });
  });

  it.each([
    [["metrics", "unknown"]],
    [["metrics"]],
    [["events"]],
    [["metrics", "dispatch", "extra"]],
  ])("blocks non-allowlisted read %s", async (path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest(`http://backoffice.test/api/telemetry/${path.join("/")}`),
      context(path),
    );

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns a safe dependency failure without leaking detail", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection secret")));

    const response = await GET(
      new NextRequest("http://backoffice.test/api/telemetry/metrics/receiving?from=2026-07-01&to=2026-07-07"),
      context(["metrics", "receiving"]),
    );
    const body = await response.json();

    expect(response.status).toBe(503);
    expect(JSON.stringify(body)).not.toContain("secret");
  });
});
