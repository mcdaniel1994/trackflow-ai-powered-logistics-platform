import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  CSRF_COOKIE_NAME,
  CSRF_HEADER_NAME,
  REFRESH_COOKIE_NAME,
  STATE_CHANGING_METHODS,
} from "@/lib/auth/constants";

type ProxyOptions = {
  baseUrl: string;
  upstreamPath: string;
  forwardCookies?: boolean;
  relaySetCookie?: boolean;
};

const UPSTREAM_TIMEOUT_MS = 15_000;

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "set-cookie",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function buildURL(request: NextRequest, baseUrl: string, upstreamPath: string) {
  const base = baseUrl.replace(/\/$/, "");
  const path = upstreamPath.startsWith("/") ? upstreamPath : `/${upstreamPath}`;
  const upstream = new URL(`${base}${path}`);
  upstream.search = request.nextUrl.search;
  return upstream;
}

function isStateChanging(method: string) {
  return STATE_CHANGING_METHODS.has(method.toUpperCase());
}

function requestHeaders(request: NextRequest, options: ProxyOptions) {
  const headers = new Headers();
  const accept = request.headers.get("accept");
  const contentType = request.headers.get("content-type");

  if (accept) {
    headers.set("Accept", accept);
  }

  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  if (options.forwardCookies !== false) {
    const cookie = request.headers.get("cookie");
    if (cookie) {
      headers.set("Cookie", cookie);
    }
  }

  if (isStateChanging(request.method)) {
    const csrfHeader = request.headers.get(CSRF_HEADER_NAME);
    if (csrfHeader) {
      headers.set(CSRF_HEADER_NAME, csrfHeader);
    }
  }

  return headers;
}

async function requestBody(request: NextRequest) {
  if (request.method === "GET" || request.method === "HEAD") {
    return undefined;
  }

  return request.arrayBuffer();
}

function copyResponseHeaders(upstream: Response) {
  const headers = new Headers();

  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  return headers;
}

function setCookieHeaders(upstream: Response) {
  const responseHeaders = upstream.headers as Headers & {
    getSetCookie?: () => string[];
  };

  const cookies = responseHeaders.getSetCookie?.();
  if (cookies?.length) {
    return cookies;
  }

  const combined = upstream.headers.get("set-cookie");
  return combined ? [combined] : [];
}

function isTimeoutError(error: unknown) {
  if (!error || typeof error !== "object" || !("name" in error)) {
    return false;
  }

  const name = (error as { name?: unknown }).name;
  return name === "AbortError" || name === "TimeoutError";
}

export function appendClearAuthCookies(response: NextResponse) {
  const secure = (process.env.AUTH_COOKIE_SECURE ?? "false").toLowerCase() === "true";
  const secureFlag = secure ? "; Secure" : "";

  response.headers.append(
    "Set-Cookie",
    `${ACCESS_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax${secureFlag}`,
  );
  response.headers.append(
    "Set-Cookie",
    `${REFRESH_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax${secureFlag}`,
  );
  response.headers.append(
    "Set-Cookie",
    `${CSRF_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secureFlag}`,
  );
}

export async function proxyRequest(request: NextRequest, options: ProxyOptions) {
  let upstream: Response;

  try {
    upstream = await fetch(buildURL(request, options.baseUrl, options.upstreamPath), {
      method: request.method,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: requestHeaders(request, options),
      body: await requestBody(request),
    });
  } catch (error) {
    if (isTimeoutError(error)) {
      return NextResponse.json({ detail: "Service timed out" }, { status: 504 });
    }

    return NextResponse.json({ detail: "Service temporarily unavailable" }, { status: 503 });
  }

  const response = new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: copyResponseHeaders(upstream),
  });

  if (options.relaySetCookie !== false) {
    for (const cookie of setCookieHeaders(upstream)) {
      response.headers.append("Set-Cookie", cookie);
    }
  }

  return response;
}
