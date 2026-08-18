import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = { params: Promise<{ path?: string[] }> };

const TRACE_ID = /^[A-Za-z0-9_-]{1,64}$/;
const SESSION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const RUN_LIST_QUERY = new Set(["agent_name", "status", "limit"]);

function allowlistedPath(method: string, path: string[]) {
  if (method === "POST") {
    // Writes are limited to one agent turn or creation of one owner-scoped chat session.
    if (path.length === 1 && path[0] === "query") return "/agent/query";
    if (path.length === 2 && path[0] === "chat" && path[1] === "sessions") return "/chat/sessions";
    return null;
  }
  if (method !== "GET") return null;
  if (path.length === 1 && path[0] === "runs") return "/agents/runs";
  if (path.length === 2 && path[0] === "runs" && TRACE_ID.test(path[1])) {
    return `/agents/runs/${encodeURIComponent(path[1])}`;
  }
  if (path.length === 2 && path[0] === "chat" && path[1] === "sessions") return "/chat/sessions";
  if (path.length === 3 && path[0] === "chat" && path[1] === "sessions" && SESSION_ID.test(path[2])) {
    return `/chat/sessions/${encodeURIComponent(path[2])}`;
  }
  return null;
}

function safeError(status: number, upstreamPath: string) {
  if (status === 401) return "Not authenticated";
  if (status === 403) return "Not authorized";
  if (status === 404) return upstreamPath.startsWith("/chat/sessions") ? "Chat session not found" : "Run not found";
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
    return NextResponse.json({ detail: safeError(response.status, upstreamPath) }, { status: response.status });
  }
  return response;
}

export const GET = handler;
export const POST = handler;
