import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

const ALLOWED_ROUTES = new Map([
  ["GET clients", "/inventory/clients"],
  ["POST clients", "/inventory/clients"],
  ["PATCH clients/:id", "/inventory/clients/:id"],
  ["GET products", "/inventory/products"],
  ["POST products", "/inventory/products"],
  ["GET products/:id", "/inventory/products/:id"],
  ["PATCH products/:id", "/inventory/products/:id"],
  ["POST orders/inbound", "/inventory/orders/inbound"],
  ["POST orders/outbound", "/inventory/orders/outbound"],
  ["GET orders", "/inventory/orders"],
]);

function allowlistedPath(method: string, path: string[]) {
  const joined = path.join("/");
  let routeKey = `${method} ${joined}`;
  if ((method === "GET" || method === "PATCH") && path.length === 2 && path[0] === "products" && /^\d+$/.test(path[1])) {
    routeKey = `${method} products/:id`;
  } else if (
    method === "PATCH" &&
    path.length === 2 &&
    path[0] === "clients" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(path[1])
  ) {
    routeKey = "PATCH clients/:id";
  }
  const template = ALLOWED_ROUTES.get(routeKey);

  if (!template) {
    return null;
  }

  // Only validated numeric/UUID identifiers are interpolated; arbitrary paths stay unreachable.
  if (template === "/inventory/products/:id") return `/inventory/products/${encodeURIComponent(path[1])}`;
  if (template === "/inventory/clients/:id") return `/inventory/clients/${encodeURIComponent(path[1])}`;
  return template;
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
export const PATCH = handler;
