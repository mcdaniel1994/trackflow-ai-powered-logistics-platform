import { NextRequest } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { incidentProcessorAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

async function handler(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  const suffix = path.length ? `/${path.map(encodeURIComponent).join("/")}` : "";

  return proxyRequest(request, {
    baseUrl: incidentProcessorAPIURL(),
    upstreamPath: `/api/incidents${suffix}`,
    forwardCookies: true,
    relaySetCookie: false,
  });
}

export const GET = handler;
export const POST = handler;
