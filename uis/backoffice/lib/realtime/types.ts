import type { RfpTicketStatus } from "@/lib/rfp/types";

export type RealtimeConnectionState = "connecting" | "connected" | "reconnecting" | "closed";

export interface ServerSentEvent {
  id: string | null;
  event: string;
  data: string;
}

export interface RfpTicketCreatedEvent {
  ticket_id: string;
  rfp_id: string;
  client_name: string | null;
  client_country: string | null;
  services_requested: string[];
  status: RfpTicketStatus;
  created_at: string;
}
