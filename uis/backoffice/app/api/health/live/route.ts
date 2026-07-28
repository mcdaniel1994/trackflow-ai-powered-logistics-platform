import { NextResponse } from "next/server";

export async function GET() {
  // Reaching this route proves only that the Next.js process can serve requests.
  return NextResponse.json({ status: "alive" });
}
