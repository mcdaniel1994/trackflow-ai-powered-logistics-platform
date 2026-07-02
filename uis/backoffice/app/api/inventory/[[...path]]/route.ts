import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

const ALLOWED_ROUTES = new Map([
  ["GET products", "/inventory/products"],
  ["GET products/:id", "/inventory/products/:id"],
  ["POST orders/inbound", "/inventory/orders/inbound"],
  ["POST orders/outbound", "/inventory/orders/outbound"],
  ["GET orders", "/inventory/orders"],
]);

function allowlistedPath(method: string, path: string[]) {
  const joined = path.join("/");
  const routeKey =
    method === "GET" && path.length === 2 && path[0] === "products" && /^\d+$/.test(path[1])
      ? "GET products/:id"
      : `${method} ${joined}`;
  const template = ALLOWED_ROUTES.get(routeKey);

  if (!template) {
    return null;
  }

  // Only the numeric product ID is interpolated; arbitrary upstream paths remain unreachable.
  return template === "/inventory/products/:id"
    ? `/inventory/products/${encodeURIComponent(path[1])}`
    : template;
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
export const POST = handler;
