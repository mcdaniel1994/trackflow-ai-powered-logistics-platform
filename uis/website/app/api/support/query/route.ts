import { NextResponse } from "next/server";
import { boundedJson, sameOrigin } from "@/lib/server/public-http";

export const maxDuration = 60;
export async function POST(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json({ code: "forbidden" }, { status: 403 });
  const secret = process.env.WEBSITE_GATEWAY_SECRET;
  const gateway = process.env.SUPPORT_GATEWAY_URL;
  if (process.env.PUBLIC_SUPPORT_ENABLED !== "true")
    return NextResponse.json({ code: "not_enabled" }, { status: 503 });
  if (!secret || !gateway)
    return NextResponse.json({ code: "unavailable" }, { status: 503 });
  let data: Record<string, unknown>;
  try {
    data = await boundedJson(request, 32768);
  } catch {
    return NextResponse.json({ code: "validation" }, { status: 400 });
  }
  if (
    Object.keys(data).some(
      (key) =>
        !["question", "language", "policy_country", "recent_context"].includes(
          key,
        ),
    )
  )
    return NextResponse.json({ code: "validation" }, { status: 422 });
  try {
    const response = await fetch(
      `${gateway.replace(/\/$/, "")}/api/public-support/query`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-website-gateway-secret": secret,
        },
        body: JSON.stringify(data),
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(40000),
      },
    );
    if (!response.ok) {
      const status = [400, 422, 429, 503, 504].includes(response.status)
        ? response.status
        : 503;
      return NextResponse.json(
        {
          code:
            status === 429
              ? "busy"
              : status === 400 || status === 422
                ? "validation"
                : "unavailable",
        },
        { status, headers: status === 429 ? { "Retry-After": "60" } : {} },
      );
    }
    const result = await response.json();
    if (
      typeof result.answer !== "string" ||
      result.answer.length > 16000 ||
      !["answered", "clarify", "contact", "rejected", "no_context"].includes(
        result.outcome,
      )
    )
      throw new Error("invalid_response");
    return NextResponse.json(
      {
        answer: result.answer,
        outcome: result.outcome,
        contact_path: "/#contact",
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    console.warn("public_support.website outcome=unavailable");
    return NextResponse.json({ code: "unavailable" }, { status: 503 });
  }
}
