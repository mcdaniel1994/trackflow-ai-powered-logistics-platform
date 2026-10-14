/** Public forms never forward cookies, user-selected URLs, or raw upstream errors. */
export async function boundedJson(
  request: Request,
  limit = 16384,
): Promise<Record<string, unknown>> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error("invalid_body");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw new Error("invalid_body");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  const data: unknown = JSON.parse(new TextDecoder().decode(bytes));
  if (!data || typeof data !== "object" || Array.isArray(data))
    throw new Error("invalid_body");
  return data as Record<string, unknown>;
}
export function sameOrigin(request: Request) {
  // Next.js may normalize the internal request URL to localhost behind its server.
  // The browser's Host and Origin must agree; forwarded host is never accepted.
  const url = new URL(request.url);
  const host = request.headers.get("host") ?? url.host;
  const protocol =
    request.headers.get("x-forwarded-proto") ?? url.protocol.slice(0, -1);
  return (
    ["http", "https"].includes(protocol) &&
    request.headers.get("origin") === `${protocol}://${host}`
  );
}
