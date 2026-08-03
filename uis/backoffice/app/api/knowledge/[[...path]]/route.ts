import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

// Only the single question endpoint is reachable; arbitrary upstream paths stay unreachable.
const ALLOWED_ROUTES = new Map([["POST query", "/knowledge/query"]]);

function allowlistedPath(method: string, path: string[]) {
  return ALLOWED_ROUTES.get(`${method} ${path.join("/")}`) ?? null;
}

async function handler(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  const upstreamPath = allowlistedPath(request.method, path);

  if (!upstreamPath) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  return proxyRequest(request, {
    baseUrl: centralAPIURL(),
    upstreamPath,
    forwardCookies: true,
    relaySetCookie: false,
  });
}

export const POST = handler;
