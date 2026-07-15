// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import * as reportingRoute from "@/app/api/reporting/[[...path]]/route";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

const { GET, POST } = reportingRoute;

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

  it("forwards CSRF only through the allowlisted pipeline queue POST", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"run_id":"run-1","status":"requested"}', { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("http://backoffice.test/api/reporting/pipeline-runs", {
        method: "POST",
        body: JSON.stringify({ week_start: "2026-07-13", force_refresh: true }),
        headers: {
          Cookie: "trackflow_access=access; trackflow_csrf=csrf",
          "Content-Type": "application/json",
          [CSRF_HEADER_NAME]: "csrf",
        },
      }),
      context(["pipeline-runs"]),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;

    expect(response.status).toBe(202);
    expect(headers.get(CSRF_HEADER_NAME)).toBe("csrf");
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/reporting/pipeline-runs");
  });

  it.each([
    ["GET", ["pipeline-runs"]],
    ["POST", ["pipeline-runs", "latest"]],
    ["GET", ["weekly-warehouse-client-performance", "extra"]],
    ["DELETE", ["pipeline-runs"]],
  ])("blocks non-allowlisted %s routes without an upstream call", async (method, path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(`http://backoffice.test/api/reporting/${path.join("/")}`, { method });
    const response = method === "POST" ? await POST(request, context(path)) : await GET(request, context(path));
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
