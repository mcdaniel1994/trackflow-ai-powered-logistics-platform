// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import * as reportingRoute from "@/app/api/reporting/[[...path]]/route";

const { GET } = reportingRoute;

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("reporting BFF", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.CENTRAL_API_URL;
  });

  it("allowlists both reporting reads and forwards query parameters and cookies", async () => {
    process.env.CENTRAL_API_URL = "http://central.test/";
    const fetchMock = vi.fn().mockImplementation(async () => new Response('{"entries":[]}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://backoffice.test/api/reporting/weekly-warehouse-client-performance?week_start=2026-07-13", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context(["weekly-warehouse-client-performance"]),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe(
      "http://central.test/reporting/weekly-warehouse-client-performance?week_start=2026-07-13",
    );
    expect(headers.get("Cookie")).toContain("trackflow_access=access");

    const latest = await GET(
      new NextRequest("http://backoffice.test/api/reporting/pipeline-runs/latest", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context(["pipeline-runs", "latest"]),
    );
    expect(latest.status).toBe(200);
    expect(fetchMock.mock.calls[1][0].toString()).toBe("http://central.test/reporting/pipeline-runs/latest");
  });

  it("no longer exposes a POST handler (manual pipeline triggering removed)", () => {
    // Manual Run now / Force refresh were removed from the Back Office (final-polish 2.3); the BFF is
    // read-only. Central API still owns POST /reporting/pipeline-runs for scheduled/CLI dispatch.
    expect("POST" in reportingRoute).toBe(false);
  });

  it.each([
    ["GET", ["pipeline-runs"]],
    ["GET", ["pipeline-runs", "run"]],
    ["GET", ["weekly-warehouse-client-performance", "extra"]],
  ])("blocks non-allowlisted %s routes without an upstream call", async (_method, path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(`http://backoffice.test/api/reporting/${path.join("/")}`, { method: "GET" });
    const response = await GET(request, context(path));
    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns a safe dependency failure", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("database password secret")));
    const response = await GET(
      new NextRequest("http://backoffice.test/api/reporting/pipeline-runs/latest"),
      context(["pipeline-runs", "latest"]),
    );
    expect(response.status).toBe(503);
    expect(JSON.stringify(await response.json())).not.toContain("secret");
  });
});
