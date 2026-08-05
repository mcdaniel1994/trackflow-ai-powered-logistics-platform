import { fetchWithAuth } from "@/lib/auth/client-http";
import type { RfpAPIError, RfpTicketDetail, RfpTicketStatus, RfpTicketSummary } from "@/lib/rfp/types";

const API_PATH = "/api/rfp";

function fallbackMessage(status: number) {
  if (status === 400) return "That file could not be read as an RFP PDF.";
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 404) return "This RFP ticket is no longer available.";
  if (status === 415) return "Only PDF documents are accepted.";
  if (status === 503) return "The RFP workflow is temporarily unavailable.";
  if (status === 504) return "The RFP workflow timed out. Please try again.";
  return "The RFP workflow could not be reached. Please try again.";
}

export function rfpError(error: unknown): RfpAPIError {
  if (error && typeof error === "object" && "message" in error && "status" in error) {
    return error as RfpAPIError;
  }
  return { message: fallbackMessage(0), status: 0 };
}

async function request<T>(path: string): Promise<T> {
  const response = await fetchWithAuth(`${API_PATH}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw { message: fallbackMessage(response.status), status: response.status } satisfies RfpAPIError;
  }
  return (await response.json()) as T;
}

export function getRfpTickets(filters: { status?: RfpTicketStatus } = {}) {
  const query = new URLSearchParams({ limit: "200" });
  if (filters.status) query.set("status", filters.status);
  return request<RfpTicketSummary[]>(`/tickets?${query}`);
}

export function getRfpTicket(ticketId: string) {
  return request<RfpTicketDetail>(`/tickets/${encodeURIComponent(ticketId)}`);
}

export async function uploadRfp(file: File): Promise<RfpTicketSummary> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetchWithAuth(`${API_PATH}/tickets`, {
    method: "POST",
    body,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw { message: fallbackMessage(response.status), status: response.status } satisfies RfpAPIError;
  }
  return (await response.json()) as RfpTicketSummary;
}
