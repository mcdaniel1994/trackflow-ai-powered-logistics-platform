import { NextRequest } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

async function handler(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  const joined = path.join("/");
  const isNumericDetail = path.length === 1 && /^\d+$/.test(path[0]);
  const isStatusUpdate = path.length === 2 && /^\d+$/.test(path[0]) && path[1] === "status";
  const allowed =
    (request.method === "GET" && (path.length === 0 || joined === "summary" || isNumericDetail)) ||
    (request.method === "POST" && path.length === 0) ||
    (request.method === "PATCH" && isStatusUpdate);

  if (!allowed) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const suffix = path.length ? `/${path.map(encodeURIComponent).join("/")}` : "";
  return proxyRequest(request, {
    baseUrl: centralAPIURL(),
    upstreamPath: `/api/incidents${suffix}`,
    forwardCookies: true,
    relaySetCookie: false,
  });
}

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
