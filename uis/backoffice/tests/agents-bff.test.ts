// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import * as agentsRoute from "@/app/api/agents/[[...path]]/route";

const { GET, POST } = agentsRoute;
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("Agent OS BFF", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.CENTRAL_API_URL;
  });

  it("exposes only GET reads and a single POST write; rejects other methods and non-allowlisted paths", async () => {
    // The only write path is POST /agent/query; PATCH/DELETE stay unimplemented.
    expect("PATCH" in agentsRoute).toBe(false);
    expect("DELETE" in agentsRoute).toBe(false);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    // GET may not reach the write-only "query" path, nor any other non-allowlisted path.
    for (const path of [["guardrails", "summary"], ["runs", "trace/id"], ["runs", "ok", "extra"], ["query"]]) {
      const response = await GET(new NextRequest(`http://backoffice.test/api/agents/${path.join("/")}`), context(path));
      expect(response.status).toBe(404);
    }
    // POST may only reach "query"; other POST paths 404.
    for (const path of [["runs"], ["runs", "abc"], ["query", "extra"], ["guardrails", "summary"]]) {
      const response = await POST(
        new NextRequest(`http://backoffice.test/api/agents/${path.join("/")}`, { method: "POST" }),
        context(path),
      );
      expect(response.status).toBe(404);
    }
    const query = await GET(
      new NextRequest("http://backoffice.test/api/agents/runs?upstream_debug=true"),
      context(["runs"]),
    );
    expect(query.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards a POST /agent/query write with auth cookies to the agent graph", async () => {
    process.env.CENTRAL_API_URL = "http://central.test/";
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response('{"answer":"ok","trace_id":"t","conversation_id":"c"}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest("http://backoffice.test/api/agents/query", {
        method: "POST",
        headers: { Cookie: "trackflow_access=access", "X-CSRF-Token": "csrf" },
        body: JSON.stringify({ question: "status of ticket 1?" }),
      }),
      context(["query"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/agent/query");
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Cookie")).toContain("trackflow_access=access");
  });

  it("forwards only an allowlisted list request with auth cookies and filters", async () => {
    process.env.CENTRAL_API_URL = "http://central.test/";
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest("http://backoffice.test/api/agents/runs?agent_name=cx&status=ok", {
        headers: { Cookie: "trackflow_access=access" },
      }),
      context(["runs"]),
    );
    const headers = fetchMock.mock.calls[0][1].headers as Headers;

    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://central.test/agents/runs?agent_name=cx&status=ok");
    expect(headers.get("Cookie")).toContain("trackflow_access=access");
  });

  it("preserves unauthenticated status but replaces the upstream body", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"credential=secret"}', { status: 401 })));

    const response = await GET(new NextRequest("http://backoffice.test/api/agents/runs"), context(["runs"]));
    const body = await response.json();

    expect(response.status).toBe(401);
    expect(body).toEqual({ detail: "Not authenticated" });
    expect(JSON.stringify(body)).not.toContain("secret");
  });

  it("returns safe not-found and dependency failures without upstream details", async () => {
    process.env.CENTRAL_API_URL = "http://central.test";
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('{"detail":"database password"}', { status: 404 }))
      .mockRejectedValueOnce(new Error("connection credential"));
    vi.stubGlobal("fetch", fetchMock);

    const missing = await GET(new NextRequest("http://backoffice.test/api/agents/runs/missing"), context(["runs", "missing"]));
    expect(await missing.json()).toEqual({ detail: "Run not found" });

    const failed = await GET(new NextRequest("http://backoffice.test/api/agents/runs"), context(["runs"]));
    expect(failed.status).toBe(503);
    expect(JSON.stringify(await failed.json())).not.toMatch(/credential|password/i);
  });
});
