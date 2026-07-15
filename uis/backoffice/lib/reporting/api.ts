import { fetchWithAuth } from "@/lib/auth/client-http";
import type {
  PipelineRunAccepted,
  PipelineRunRequest,
  PipelineRunsStatus,
  ReportingAPIError,
  WeeklyPerformanceReport,
} from "@/lib/reporting/types";

const API_PATH = "/api/reporting";

function fallbackMessage(status: number) {
  if (status === 400) return "Please choose an ISO week that starts on Monday.";
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "Administrator access is required to run the reporting pipeline.";
  if (status === 503) return "Reporting service is temporarily unavailable.";
  if (status === 504) return "Reporting service timed out. Please try again.";
  return `Reporting request failed with status ${status}.`;
}

async function parseError(response: Response): Promise<ReportingAPIError> {
  const error: ReportingAPIError = { message: fallbackMessage(response.status), status: response.status };
  try {
    const payload = (await response.json()) as Record<string, unknown>;
    if (typeof payload.detail === "string") {
      error.message = payload.detail;
    }
    if (payload.error && typeof payload.error === "object") {
      const envelope = payload.error as Record<string, unknown>;
      if (typeof envelope.message === "string") error.message = envelope.message;
      if (typeof envelope.code === "string") error.code = envelope.code;
    }
  } catch {
    // Keep the status-based fallback; malformed upstream bodies never reach the page.
  }
  return error;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body) headers.set("Content-Type", "application/json");
  const response = await fetchWithAuth(`${API_PATH}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export function getWeeklyPerformance(weekStart?: string) {
  const query = weekStart ? `?${new URLSearchParams({ week_start: weekStart })}` : "";
  return request<WeeklyPerformanceReport>(`/weekly-warehouse-client-performance${query}`);
}

export function getPipelineRunsStatus() {
  return request<PipelineRunsStatus>("/pipeline-runs/latest");
}

export function requestPipelineRun(input: PipelineRunRequest) {
  return request<PipelineRunAccepted>("/pipeline-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reportingError(error: unknown): ReportingAPIError {
  if (error && typeof error === "object" && "message" in error && "status" in error) {
    return error as ReportingAPIError;
  }
  return { message: "Something went wrong. Please try again.", status: 0 };
}
