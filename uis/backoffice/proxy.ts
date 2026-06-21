import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE_NAME } from "@/lib/auth/constants";
import { loginPathFor } from "@/lib/auth/redirects";

const OPEN_PAGE_PATHS = new Set(["/forgot-password", "/login", "/reset-password"]);

function isOpenPage(pathname: string) {
  return OPEN_PAGE_PATHS.has(pathname);
}

export function proxy(request: NextRequest) {
  const path = `${request.nextUrl.pathname}${request.nextUrl.search}`;

  if (isOpenPage(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  if (!request.cookies.has(ACCESS_COOKIE_NAME)) {
    return NextResponse.redirect(new URL(loginPathFor(path), request.url));
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-trackflow-path", path);

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
