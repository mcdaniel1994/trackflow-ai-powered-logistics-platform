import { NextResponse } from "next/server";
import {
  applicationErrors,
  CAREER_ROLES,
  type DemoApplication,
} from "@/lib/careers";
import { boundedJson, sameOrigin } from "@/lib/server/public-http";

export const maxDuration = 30;
export async function POST(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json({ code: "forbidden" }, { status: 403 });
  if (process.env.CAREERS_DEMO_ENABLED !== "true")
    return NextResponse.json({ code: "unavailable" }, { status: 503 });
  let value: Record<string, unknown>;
  try {
    value = await boundedJson(request);
  } catch {
    return NextResponse.json({ code: "invalid_body" }, { status: 400 });
  }
  const errors = applicationErrors(value);
  if (Object.keys(errors).length)
    return NextResponse.json(
      { code: "validation", fields: errors },
      { status: 422 },
    );
  const data = value as unknown as DemoApplication;
  const base = (
    process.env.TALENT_API_URL ?? "https://playground.4geeks.com/tracker/api/v1"
  ).replace(/\/$/, "");
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    const response = await fetch(`${base}/records`, {
      method: "POST",
      headers,
      redirect: "error",
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
      body: JSON.stringify({
        full_name: data.full_name.trim(),
        email: data.email.trim().toLowerCase(),
        position: CAREER_ROLES[data.role].en,
        experience_years: data.experience_years,
        phone: "+1-202-555-0100",
        linkedin_url: "",
        cv_url: "",
      }),
    });
    if (!response.ok) {
      console.warn(
        "careers.application_failed outcome=upstream_rejected status=%d",
        response.status,
      );
      return NextResponse.json(
        {
          code:
            response.status === 409
              ? "duplicate"
              : response.status >= 500
                ? "uncertain"
                : "unavailable",
        },
        { status: response.status === 409 ? 409 : 502 },
      );
    }
    const saved: unknown = await response.json();
    const record =
      saved && typeof saved === "object"
        ? (saved as Record<string, unknown>)
        : {};
    const id = typeof record.id === "string" ? record.id : "";
    // The published sandbox create contract owns state and application time. Confirm
    // its defaults rather than sending unsupported fields or retrying a write.
    if (
      !/^[A-Za-z0-9_-]{1,128}$/.test(id) ||
      record.status !== "received" ||
      record.stage !== "pending" ||
      typeof record.applied_at !== "string" ||
      !Number.isFinite(Date.parse(record.applied_at))
    ) {
      console.warn("careers.application_failed outcome=invalid_confirmation");
      return NextResponse.json({ code: "uncertain" }, { status: 502 });
    }
    return NextResponse.json(
      { candidate_id: id },
      { status: 201, headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    const timeout =
      error instanceof Error &&
      ["TimeoutError", "AbortError"].includes(error.name);
    console.warn(
      "careers.application_failed outcome=%s",
      timeout ? "timeout" : "connection_failure",
    );
    return NextResponse.json(
      { code: "uncertain" },
      { status: timeout ? 504 : 502 },
    );
  }
}
