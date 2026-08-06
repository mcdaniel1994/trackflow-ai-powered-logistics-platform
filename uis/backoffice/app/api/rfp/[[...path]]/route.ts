import { NextRequest, NextResponse } from "next/server";
import { proxyRequest } from "@/lib/server/proxy";
import { centralAPIURL } from "@/lib/server/service-urls";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

// Only the ticket list, a single ticket detail, and multipart upload are reachable; arbitrary
// upstream paths stay unreachable. Ticket ids are UUIDs.
const UUID_RE = /^[0-9a-fA-F-]{1,36}$/;
const DEPARTMENT_RE = /^[a-z]+$/;

function isAllowed(method: string, path: string[]): boolean {
  const isTicketDetail = path.length === 2 && path[0] === "tickets" && UUID_RE.test(path[1]);
  const isTicketsRoot = path.length === 1 && path[0] === "tickets";
  const isDocument =
    path.length === 3 && path[0] === "tickets" && UUID_RE.test(path[1]) && path[2] === "document";
  const isDecision =
    path.length === 5 &&
    path[0] === "tickets" &&
    UUID_RE.test(path[1]) &&
    path[2] === "departments" &&
    DEPARTMENT_RE.test(path[3]) &&
    path[4] === "decision";
  return (
    (method === "GET" && (isTicketsRoot || isTicketDetail || isDocument)) ||
    (method === "POST" && (isTicketsRoot || isDecision))
  );
}

async function handler(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  if (!isAllowed(request.method, path)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  const suffix = `/${path.map(encodeURIComponent).join("/")}`;
  return proxyRequest(request, {
    baseUrl: centralAPIURL(),
    upstreamPath: `/rfp${suffix}`,
    forwardCookies: true,
    relaySetCookie: false,
  });
}

export const GET = handler;
export const POST = handler;
