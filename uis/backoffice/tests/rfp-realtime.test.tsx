import { describe, expect, it, vi } from "vitest";
import type { RfpTicketSummary } from "@/lib/rfp/types";
import { eventToRfpSummary, mergeRfpSnapshot } from "@/lib/realtime/rfp-stream";
import { connectSSE, parseSSEStream, sseRetryDelay } from "@/lib/realtime/sse";
import type { RealtimeConnectionState, RfpTicketCreatedEvent } from "@/lib/realtime/types";

function byteStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

const notification: RfpTicketCreatedEvent = {
  ticket_id: "new-ticket",
  rfp_id: "RFP-NEW",
  client_name: null,
  client_country: null,
  services_requested: [],
  status: "analyzing",
  created_at: "2026-08-18T12:00:00Z",
};

const snapshotTicket: RfpTicketSummary = {
  id: "existing-ticket",
  rfp_id: "RFP-EXISTING",
  status: "done",
  client_name: "Existing client",
  client_country: "US",
  currency: "USD",
  departments_needed: ["warehouse"],
  created_at: "2026-08-17T12:00:00Z",
  updated_at: "2026-08-17T12:00:00Z",
};

describe("RFP SSE client", () => {
  it("parses fragmented frames, named events, ids, comments, CRLF, and multiline data", async () => {
    const stream = byteStream([
      ": connected\r",
      "\n\r\nid: 4\r\nevent: rfp_ticket_",
      "created\r\ndata: {\"ticket_id\":\r\ndata: \"new-ticket\"}\r\n\r\n",
    ]);
    const events = [];
    for await (const event of parseSSEStream(stream)) events.push(event);

    expect(events).toEqual([
      {
        id: "4",
        event: "rfp_ticket_created",
        data: '{"ticket_id":\n"new-ticket"}',
      },
    ]);
  });

  it("uses capped exponential backoff with jitter", () => {
    expect(sseRetryDelay(0, () => 0)).toBe(750);
    expect(sseRetryDelay(2, () => 0.5)).toBe(4000);
    expect(sseRetryDelay(20, () => 1)).toBe(37500);
  });

  it("buffers notifications across an authoritative snapshot and deduplicates by ticket_id", () => {
    const duplicate = { ...notification, ticket_id: snapshotTicket.id, rfp_id: snapshotTicket.rfp_id };
    const merged = mergeRfpSnapshot([snapshotTicket], [notification, duplicate]);

    expect(merged.map((ticket) => ticket.id)).toEqual([notification.ticket_id, snapshotTicket.id]);
    expect(merged[1]).toEqual(snapshotTicket);
    expect(eventToRfpSummary(notification)).toMatchObject({
      id: "new-ticket",
      client_name: null,
      departments_needed: null,
    });
  });

  it("recovers after failure, delivers the next stream, and cleans up on cancellation", async () => {
    const controller = new AbortController();
    const states: RealtimeConnectionState[] = [];
    const delays: number[] = [];
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(
        new Response(
          byteStream([
            'id: 1\nevent: rfp_ticket_created\ndata: {"ticket_id":"new-ticket"}\n\n',
          ]),
          { status: 200 },
        ),
      );

    await connectSSE({
      url: "/realtime/rfp/stream",
      signal: controller.signal,
      fetcher,
      random: () => 0,
      sleep: async (milliseconds) => {
        delays.push(milliseconds);
      },
      onState: (state) => states.push(state),
      onEvent: () => controller.abort(),
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(delays).toEqual([750]);
    expect(states).toEqual(["connecting", "reconnecting", "connected", "closed"]);
  });
});
