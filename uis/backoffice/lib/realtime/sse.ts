import { fetchWithAuth } from "@/lib/auth/client-http";
import type { RealtimeConnectionState, ServerSentEvent } from "@/lib/realtime/types";

export interface SSEConnectionOptions {
  url: string;
  signal: AbortSignal;
  onEvent: (event: ServerSentEvent) => void;
  onState: (state: RealtimeConnectionState) => void;
  onOpen?: () => void;
  fetcher?: typeof fetchWithAuth;
  random?: () => number;
  sleep?: (milliseconds: number, signal: AbortSignal) => Promise<void>;
}

function parseFrame(frame: string): ServerSentEvent | null {
  let id: string | null = null;
  let event = "message";
  const data: string[] = [];

  for (const line of frame.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "id" && !value.includes("\0")) id = value;
    if (field === "event") event = value;
    if (field === "data") data.push(value);
  }

  return data.length > 0 ? { id, event, data: data.join("\n") } : null;
}

export async function* parseSSEStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<ServerSentEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const cancelReader = () => void reader.cancel();
  signal?.addEventListener("abort", cancelReader, { once: true });
  try {
    while (!signal?.aborted) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = findFrameBoundary(buffer);
      while (boundary) {
        const event = parseFrame(buffer.slice(0, boundary.index).replaceAll("\r\n", "\n").replaceAll("\r", "\n"));
        buffer = buffer.slice(boundary.index + boundary.length);
        if (event) yield event;
        boundary = findFrameBoundary(buffer);
      }
      if (done) return;
    }
  } finally {
    signal?.removeEventListener("abort", cancelReader);
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

function findFrameBoundary(buffer: string): { index: number; length: number } | null {
  const candidates = ["\r\n\r\n", "\n\n", "\r\r"]
    .map((separator) => ({ index: buffer.indexOf(separator), length: separator.length }))
    .filter(({ index }) => index >= 0)
    .sort((left, right) => left.index - right.index);
  return candidates[0] ?? null;
}

export function sseRetryDelay(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(30_000, 1_000 * 2 ** Math.max(0, attempt));
  return Math.round(base * (0.75 + random() * 0.5));
}

export function abortableDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve();
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

export async function connectSSE(options: SSEConnectionOptions): Promise<void> {
  const fetcher = options.fetcher ?? fetchWithAuth;
  const sleep = options.sleep ?? abortableDelay;
  let attempt = 0;
  options.onState("connecting");

  while (!options.signal.aborted) {
    try {
      const response = await fetcher(options.url, {
        headers: { Accept: "text/event-stream" },
        cache: "no-store",
        credentials: "include",
        signal: options.signal,
        redirectOnUnauthorized: false,
      });
      if (!response.ok || !response.body) throw new Error(`SSE request failed (${response.status})`);
      options.onOpen?.();
      options.onState("connected");
      for await (const event of parseSSEStream(response.body, options.signal)) {
        attempt = 0;
        options.onEvent(event);
      }
      if (!options.signal.aborted) throw new Error("SSE stream closed");
    } catch {
      if (options.signal.aborted) break;
      options.onState("reconnecting");
      await sleep(sseRetryDelay(attempt, options.random), options.signal);
      attempt += 1;
    }
  }
  options.onState("closed");
}
