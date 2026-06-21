import { CSRF_COOKIE_NAME } from "@/lib/auth/constants";

export function readCSRFCookie() {
  if (typeof document === "undefined") {
    return "";
  }

  const csrfCookie = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${CSRF_COOKIE_NAME}=`));

  if (!csrfCookie) {
    return "";
  }

  return decodeURIComponent(csrfCookie.slice(CSRF_COOKIE_NAME.length + 1));
}
