import { NextRequest, NextResponse } from "next/server";
import {
  CSRF_COOKIE_NAME,
  CSRF_HEADER_NAME,
  STATE_CHANGING_METHODS,
} from "@/lib/auth/constants";
import { getServerSessionUser } from "@/lib/auth/session";
import { proxyRequest } from "@/lib/server/proxy";
import { talentAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

function requiresCSRF(method: string) {
  return STATE_CHANGING_METHODS.has(method.toUpperCase());
}

function hasValidCSRF(request: NextRequest) {
  const cookie = request.cookies.get(CSRF_COOKIE_NAME)?.value ?? "";
  const header = request.headers.get(CSRF_HEADER_NAME) ?? "";
  return Boolean(cookie && header && cookie === header);
}

async function handler(request: NextRequest, context: RouteContext) {
  const user = await getServerSessionUser();
  if (!user) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  if (user.must_change_password) {
    return NextResponse.json({ detail: "Password change required" }, { status: 403 });
  }

  if (requiresCSRF(request.method) && !hasValidCSRF(request)) {
    return NextResponse.json({ detail: "CSRF token missing or invalid" }, { status: 403 });
  }

  const { path = [] } = await context.params;
  const suffix = path.length ? `/${path.map(encodeURIComponent).join("/")}` : "";

  return proxyRequest(request, {
    baseUrl: talentAPIURL(),
    upstreamPath: suffix || "/",
    forwardCookies: false,
    relaySetCookie: false,
  });
}

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const DELETE = handler;
