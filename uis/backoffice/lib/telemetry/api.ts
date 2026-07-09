import { fetchWithAuth } from "@/lib/auth/client-http";
import type {
  AccessDenialMetrics,
  DateRange,
  DispatchMetrics,
  ReceivingMetrics,
  StockLossMetrics,
  TelemetryAPIError,
} from "@/lib/telemetry/types";

const API_PATH = "/api/telemetry";

function fallbackMessage(status: number) {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 400) return "Please choose a valid date range (up to 92 days).";
  if (status === 503) return "Telemetry service is temporarily unavailable.";
  if (status === 504) return "Telemetry service timed out. Please try again.";
  return `Telemetry request failed with status ${status}.`;
}

export function telemetryError(error: unknown): TelemetryAPIError {
  if (error && typeof error === "object" && "message" in error && "status" in error) {
    return error as TelemetryAPIError;
  }
  return { message: "Something went wrong. Please try again.", status: 0 };
}

async function parseError(response: Response): Promise<TelemetryAPIError> {
  const error: TelemetryAPIError = { message: fallbackMessage(response.status), status: response.status };
  try {
    const payload = (await response.json()) as Record<string, unknown>;
    if (typeof payload.detail === "string") error.message = payload.detail;
  } catch {
    // Keep the safe status-based fallback for HTML or malformed upstream bodies.
  }
  return error;
}

async function request<T>(path: string): Promise<T> {
  const response = await fetchWithAuth(`${API_PATH}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

function rangeQuery(range: DateRange) {
  return `?${new URLSearchParams({ from: range.from, to: range.to })}`;
}

export function getDispatchMetrics(range: DateRange) {
  return request<DispatchMetrics>(`/metrics/dispatch${rangeQuery(range)}`);
}

export function getReceivingMetrics(range: DateRange) {
  return request<ReceivingMetrics>(`/metrics/receiving${rangeQuery(range)}`);
}

export function getStockLossMetrics(range: DateRange) {
  return request<StockLossMetrics>(`/metrics/stock-loss${rangeQuery(range)}`);
}

export function getAccessDenialMetrics(range: DateRange) {
  return request<AccessDenialMetrics>(`/metrics/access-denials${rangeQuery(range)}`);
}

/** Default to the trailing seven UTC days, inclusive. */
export function defaultRange(): DateRange {
  const end = new Date();
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 6);
  return { from: start.toISOString().slice(0, 10), to: end.toISOString().slice(0, 10) };
}
