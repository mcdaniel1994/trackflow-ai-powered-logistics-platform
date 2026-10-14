import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { centralAPIURL } from "@/lib/server/service-urls";

/** Fixed service-to-service relay. Staff cookies, authorization and arbitrary URLs never pass. */
export async function POST(request: Request) {
  const expected = process.env.WEBSITE_GATEWAY_SECRET ?? "";
  const supplied = request.headers.get("x-website-gateway-secret") ?? "";
  const expectedBytes = Buffer.from(expected);
  const suppliedBytes = Buffer.from(supplied);
  if (
    !expected ||
    suppliedBytes.length !== expectedBytes.length ||
    !timingSafeEqual(suppliedBytes, expectedBytes)
  )
    return NextResponse.json({ code: "forbidden" }, { status: 403 });
  if (process.env.PUBLIC_SUPPORT_ENABLED !== "true")
    return NextResponse.json({ code: "unavailable" }, { status: 503 });
  // Limit bytes before buffering/forwarding even for a service-authenticated caller.
  const reader = request.body?.getReader();
  if (!reader)
    return NextResponse.json({ code: "validation" }, { status: 400 });
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > 32768)
        return NextResponse.json({ code: "validation" }, { status: 413 });
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
  const body = Buffer.concat(chunks);
  try {
    const response = await fetch(`${centralAPIURL()}/public-support/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-website-gateway-secret": expected,
      },
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(35000),
    });
    if (!response.ok) {
      const status = [400, 422, 429, 503, 504].includes(response.status)
        ? response.status
        : 503;
      return NextResponse.json(
        {
          code:
            status === 429
              ? "busy"
              : status === 422 || status === 400
                ? "validation"
                : "unavailable",
        },
        { status, headers: status === 429 ? { "Retry-After": "60" } : {} },
      );
    }
    const value = await response.json();
    if (
      typeof value.answer !== "string" ||
      value.answer.length > 16000 ||
      !["answered", "clarify", "contact", "rejected", "no_context"].includes(
        value.outcome,
      )
    )
      throw new Error("invalid_response");
    return NextResponse.json(
      {
        answer: value.answer,
        outcome: value.outcome,
        contact_path: "/#contact",
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    console.warn(
      "public_support.gateway outcome=%s",
      error instanceof Error && error.name === "TimeoutError"
        ? "timeout"
        : "unavailable",
    );
    return NextResponse.json(
      { code: "unavailable" },
      {
        status:
          error instanceof Error && error.name === "TimeoutError" ? 504 : 503,
      },
    );
  }
}
