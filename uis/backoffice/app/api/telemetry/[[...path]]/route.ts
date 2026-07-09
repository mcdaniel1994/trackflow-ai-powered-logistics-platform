import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

// Read-only reporting surface. Only these aggregate GET routes are reachable; there is
// no telemetry ingest path in Phase 1, so arbitrary upstream paths remain unreachable.
const ALLOWED_ROUTES = new Map([
  ["GET metrics/dispatch", "/telemetry/metrics/dispatch"],
  ["GET metrics/receiving", "/telemetry/metrics/receiving"],
  ["GET metrics/stock-loss", "/telemetry/metrics/stock-loss"],
  ["GET metrics/access-denials", "/telemetry/metrics/access-denials"],
]);

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

export const GET = handler;
