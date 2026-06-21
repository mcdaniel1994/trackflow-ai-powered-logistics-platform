import { NextRequest, NextResponse } from "next/server";
import { appendClearAuthCookies, proxyRequest } from "@/lib/server/proxy";
import { identityAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

const AUTH_ROUTE_METHODS: Record<string, Set<string>> = {
  "forgot-password": new Set(["POST"]),
  login: new Set(["POST"]),
  refresh: new Set(["POST"]),
  logout: new Set(["POST"]),
  me: new Set(["GET"]),
  "change-password": new Set(["POST"]),
  "reset-password": new Set(["POST"]),
};

function notFound() {
  return NextResponse.json({ detail: "Not found" }, { status: 404 });
}

async function handler(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  const route = path.join("/");
  const allowedMethods = AUTH_ROUTE_METHODS[route];

  if (!allowedMethods?.has(request.method)) {
    return notFound();
  }

  const response = await proxyRequest(request, {
    baseUrl: identityAPIURL(),
    upstreamPath: `/auth/${route}`,
    forwardCookies: true,
    relaySetCookie: true,
  });

  if (route === "logout") {
    appendClearAuthCookies(response);
    if (response.status === 401) {
      const cleared = NextResponse.json({ status: "ok" });
      appendClearAuthCookies(cleared);
      return cleared;
    }
  }

  if (route === "me" && response.status === 401) {
    appendClearAuthCookies(response);
  }

  return response;
}

export const GET = handler;
export const POST = handler;
