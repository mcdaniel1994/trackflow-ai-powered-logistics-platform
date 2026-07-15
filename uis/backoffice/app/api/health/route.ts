import { NextResponse } from "next/server";
import { centralAPIURL, identityAPIURL } from "@/lib/server/service-urls";

export async function GET() {
  try {
    const responses = await Promise.all([
      fetch(`${identityAPIURL()}/health`, { cache: "no-store", signal: AbortSignal.timeout(4_000) }),
      fetch(`${centralAPIURL()}/health/ready`, { cache: "no-store", signal: AbortSignal.timeout(4_000) }),
    ]);
    if (responses.every((response) => response.ok)) {
      return NextResponse.json({ status: "ok" });
    }
  } catch {
    // Public health never reflects dependency URLs, bodies, or exception details.
  }
  return NextResponse.json({ status: "unavailable" }, { status: 503 });
}
