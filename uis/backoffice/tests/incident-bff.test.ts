// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, PATCH, POST } from "@/app/api/incidents/[[...path]]/route";
import { CSRF_HEADER_NAME } from "@/lib/auth/constants";

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("incident BFF", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.CENTRAL_API_URL;
  });

  it("routes allowlisted incident reads to Central API with filters", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"items":[],"total":0,"limit":50,"offset":0}', {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://backoffice.test/api/incidents?status=open", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context([]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/api/incidents?status=open");
  });

  it("forwards CSRF for create and status updates", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"id":1}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const headers = {
      Cookie: "trackflow_access=access; trackflow_csrf=csrf",
      "Content-Type": "application/json",
      [CSRF_HEADER_NAME]: "csrf",
    };

    await POST(
      new NextRequest("http://backoffice.test/api/incidents", {
        method: "POST",
        body: "{}",
        headers,
      }),
      context([]),
    );
    await PATCH(
      new NextRequest("http://backoffice.test/api/incidents/1/status", {
        method: "PATCH",
        body: '{"status":"in_progress"}',
        headers,
      }),
      context(["1", "status"]),
    );

    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/api/incidents");
    expect(fetchMock.mock.calls[1][0].toString()).toBe("http://central.test/api/incidents/1/status");
    expect((fetchMock.mock.calls[1][1].headers as Headers).get(CSRF_HEADER_NAME)).toBe("csrf");
  });

  it.each([
    ["GET", ["analyze"]],
    ["GET", ["not-a-number"]],
    ["POST", ["summary"]],
    ["PATCH", ["1"]],
    ["PATCH", ["text", "status"]],
  ])("blocks non-allowlisted %s routes", async (method, path) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest(`http://backoffice.test/api/incidents/${path.join("/")}`, { method });
    const response =
      method === "GET"
        ? await GET(request, context(path))
        : method === "POST"
          ? await POST(request, context(path))
          : await PATCH(request, context(path));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [new Error("connection secret"), 503, "Service temporarily unavailable"],
    [Object.assign(new Error("timeout secret"), { name: "TimeoutError" }), 504, "Service timed out"],
  ])("returns safe upstream failures", async (failure, status, detail) => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure));
    const response = await GET(new NextRequest("http://backoffice.test/api/incidents"), context([]));
    const body = await response.json();

    expect(response.status).toBe(status);
    expect(body).toEqual({ detail });
    expect(JSON.stringify(body)).not.toContain("secret");
  });
});

