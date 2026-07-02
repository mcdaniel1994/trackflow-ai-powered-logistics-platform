import { fetchWithAuth } from "@/lib/auth/client-http";
import type {
  Incident,
  IncidentAPIError,
  IncidentCreate,
  IncidentFilters,
  IncidentPage,
  IncidentStatus,
  IncidentSummary,
} from "./incident-types";

const API_PATH = "/api/incidents";

export class IncidentRequestError extends Error {
  constructor(public readonly detail: IncidentAPIError) {
    super(detail.message);
  }
}

async function parseError(response: Response): Promise<IncidentRequestError> {
  try {
    const payload = await response.json();
    const error = payload?.error;
    if (error && typeof error.message === "string") {
      return new IncidentRequestError({
        code: typeof error.code === "string" ? error.code : "REQUEST_FAILED",
        message: error.message,
        fields: error.fields && typeof error.fields === "object" ? error.fields : {},
      });
    }
  } catch {
    // The UI intentionally replaces malformed or technical upstream errors.
  }
  return new IncidentRequestError({
    code: "REQUEST_FAILED",
    message: "The incident service could not complete the request. Please try again.",
    fields: {},
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchWithAuth(`${API_PATH}${path}`, init);
  if (!response.ok) {
    throw await parseError(response);
  }
  return response.json() as Promise<T>;
}

export function createIncident(payload: IncidentCreate) {
  return request<Incident>("", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listIncidents(filters: IncidentFilters = {}) {
  const query = new URLSearchParams({ limit: "50", offset: "0" });
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  return request<IncidentPage>(`?${query.toString()}`);
}

export function getIncidentSummary() {
  return request<IncidentSummary>("/summary");
}

export function updateIncidentStatus(id: number, status: IncidentStatus) {
  return request<Incident>(`/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}
