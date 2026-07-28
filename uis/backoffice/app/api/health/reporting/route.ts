import { NextResponse } from "next/server";
import { centralAPIURL } from "@/lib/server/service-urls";

export async function GET() {
  try {
    const upstream = await fetch(`${centralAPIURL()}/health/reporting`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4_000),
    });
    const payload: unknown = await upstream.json();
    if (payload && typeof payload === "object") {
      return NextResponse.json(payload, { status: upstream.status });
    }
  } catch {
    // Return one stable classification without dependency URLs or exception detail.
  }
  return NextResponse.json(
    { status: "not_verified", check: "reporting_dependency" },
    { status: 503 },
  );
}
