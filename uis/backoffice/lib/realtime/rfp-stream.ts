"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getRfpTickets, rfpError } from "@/lib/rfp/api";
import type { RfpTicketSummary } from "@/lib/rfp/types";
import { connectSSE } from "@/lib/realtime/sse";
import type { RealtimeConnectionState, RfpTicketCreatedEvent, ServerSentEvent } from "@/lib/realtime/types";

function realtimePath(): string {
  return "/realtime/rfp/stream";
}

export function eventToRfpSummary(event: RfpTicketCreatedEvent): RfpTicketSummary {
  return {
    id: event.ticket_id,
    rfp_id: event.rfp_id,
    status: event.status,
    client_name: event.client_name,
    client_country: event.client_country,
    currency: null,
    departments_needed: null,
    created_at: event.created_at,
    updated_at: event.created_at,
  };
}

export function mergeRfpSnapshot(
  snapshot: RfpTicketSummary[],
  notifications: RfpTicketCreatedEvent[],
): RfpTicketSummary[] {
  const seen = new Set(snapshot.map((ticket) => ticket.id));
  const additions: RfpTicketSummary[] = [];
  for (const notification of notifications) {
    if (!seen.has(notification.ticket_id)) {
      additions.unshift(eventToRfpSummary(notification));
      seen.add(notification.ticket_id);
    }
  }
  return [...additions, ...snapshot];
}

function parseRfpEvent(event: ServerSentEvent): RfpTicketCreatedEvent | null {
  if (event.event !== "rfp_ticket_created") return null;
  try {
    const value = JSON.parse(event.data) as Partial<RfpTicketCreatedEvent>;
    if (!value.ticket_id || !value.rfp_id || !value.created_at || value.status !== "analyzing") return null;
    return {
      ticket_id: value.ticket_id,
      rfp_id: value.rfp_id,
      client_name: value.client_name ?? null,
      client_country: value.client_country ?? null,
      services_requested: Array.isArray(value.services_requested) ? value.services_requested.map(String) : [],
      status: value.status,
      created_at: value.created_at,
    };
  } catch {
    return null;
  }
}

export function useRfpTicketStream(refreshNonce: number) {
  const [tickets, setTickets] = useState<RfpTicketSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState<RealtimeConnectionState>("connecting");
  const [newTicketId, setNewTicketId] = useState<string | null>(null);
  const buffering = useRef(true);
  const bufferedEvents = useRef<RfpTicketCreatedEvent[]>([]);
  const snapshotVersion = useRef(0);

  const refreshSnapshot = useCallback(async () => {
    const version = ++snapshotVersion.current;
    buffering.current = true;
    bufferedEvents.current = [];
    try {
      const snapshot = await getRfpTickets();
      if (version !== snapshotVersion.current) return;
      setTickets(mergeRfpSnapshot(snapshot, bufferedEvents.current));
      setError(null);
    } catch (caught) {
      if (version === snapshotVersion.current) setError(rfpError(caught).message);
    } finally {
      if (version === snapshotVersion.current) buffering.current = false;
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void connectSSE({
      url: realtimePath(),
      signal: controller.signal,
      onState: setConnection,
      onOpen: () => void refreshSnapshot(),
      onEvent: (raw) => {
        const event = parseRfpEvent(raw);
        if (!event) return;
        setError(null);
        setNewTicketId(event.ticket_id);
        if (buffering.current) bufferedEvents.current.push(event);
        else setTickets((current) => mergeRfpSnapshot(current ?? [], [event]));
      },
    });
    return () => controller.abort();
  }, [refreshSnapshot]);

  useEffect(() => {
    if (refreshNonce > 0) void refreshSnapshot();
  }, [refreshNonce, refreshSnapshot]);

  return {
    tickets: tickets ?? [],
    loading: tickets === null && error === null,
    error,
    connection,
    newTicketId,
    acknowledgeTicket: () => setNewTicketId(null),
  };
}
