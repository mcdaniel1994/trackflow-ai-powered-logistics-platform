import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = { params: Promise<{ path?: string[] }> };

const TRACE_ID = /^[A-Za-z0-9_-]{1,64}$/;
const RUN_LIST_QUERY = new Set(["agent_name", "status", "limit"]);

function allowlistedPath(method: string, path: string[]) {
  if (method === "POST") {
    // The single write path: orchestrate one question through the LangGraph agent.
    if (path.length === 1 && path[0] === "query") return "/agent/query";
    return null;
  }
  if (method !== "GET") return null;
  if (path.length === 1 && path[0] === "runs") return "/agents/runs";
  if (path.length === 2 && path[0] === "runs" && TRACE_ID.test(path[1])) {
    return `/agents/runs/${encodeURIComponent(path[1])}`;
  }
  return null;
}

function safeError(status: number) {
  if (status === 401) return "Not authenticated";
  if (status === 403) return "Not authorized";
  if (status === 404) return "Run not found";
  if (status === 504) return "Service timed out";
  return "Service temporarily unavailable";
}

async function handler(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  const upstreamPath = allowlistedPath(request.method, path);
  if (!upstreamPath) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  const allowedQuery = path.length === 1 ? RUN_LIST_QUERY : new Set<string>();
  if ([...request.nextUrl.searchParams.keys()].some((key) => !allowedQuery.has(key))) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  const response = await proxyRequest(request, {
    baseUrl: centralAPIURL(),
    upstreamPath,
    forwardCookies: true,
    relaySetCookie: false,
  });
  if (!response.ok) {
    return NextResponse.json({ detail: safeError(response.status) }, { status: response.status });
  }
  return response;
}

export const GET = handler;
export const POST = handler;
