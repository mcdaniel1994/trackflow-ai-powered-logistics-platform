import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

// Read-only. Manual pipeline triggering was removed from the Back Office (final-polish 2.3):
// it mutates real reporting state from a recorded/demoed UI. Scheduled and CLI dispatch keep the
// Central API POST /reporting/pipeline-runs endpoint; the Back Office simply no longer exposes it.
const ALLOWED_ROUTES = new Map([
  ["GET weekly-warehouse-client-performance", "/reporting/weekly-warehouse-client-performance"],
  ["GET pipeline-runs/latest", "/reporting/pipeline-runs/latest"],
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
