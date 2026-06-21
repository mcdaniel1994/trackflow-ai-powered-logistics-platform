const BLOCKED_NEXT_PREFIXES = [
  "/api",
  "/forgot-password",
  "/login",
  "/reset-password",
];

export function safeNextPath(value: string | null | undefined, fallback = "/") {
  if (!value) {
    return fallback;
  }

  let decoded = value;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    decoded = value;
  }

  if (!decoded.startsWith("/") || decoded.startsWith("//")) {
    return fallback;
  }

  if (
    BLOCKED_NEXT_PREFIXES.some(
      (prefix) => decoded === prefix || decoded.startsWith(`${prefix}/`) || decoded.startsWith(`${prefix}?`),
    )
  ) {
    return fallback;
  }

  return decoded;
}

export function loginPathFor(nextPath: string | null | undefined) {
  const safeNext = safeNextPath(nextPath, "");
  return safeNext ? `/login?next=${encodeURIComponent(safeNext)}` : "/login";
}
