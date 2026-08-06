import { fetchWithAuth } from "@/lib/auth/client-http";
import type {
  AgentAnswer,
  AgentAPIError,
  AgentRunDetail,
  AgentRunStatus,
  AgentRunSummary,
} from "@/lib/agents/types";

const API_PATH = "/api/agents";

function askFallbackMessage(status: number) {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You don't have access to the assistant.";
  if (status === 422) return "Please enter a question.";
  if (status === 502) return "The assistant is temporarily unavailable.";
  if (status === 503) return "The assistant is not available right now.";
  if (status === 504) return "The assistant timed out. Please try again.";
  return `The assistant failed with status ${status}.`;
}

function fallbackMessage(status: number) {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 404) return "This agent run is no longer available.";
  if (status === 503) return "Agent observability is temporarily unavailable.";
  if (status === 504) return "Agent observability timed out. Please try again.";
  return "Agent observability could not be loaded. Please try again.";
}

export function agentError(error: unknown): AgentAPIError {
  if (error && typeof error === "object" && "message" in error && "status" in error) {
    return error as AgentAPIError;
  }
  return { message: fallbackMessage(0), status: 0 };
}

async function request<T>(path: string): Promise<T> {
  const response = await fetchWithAuth(`${API_PATH}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw { message: fallbackMessage(response.status), status: response.status } satisfies AgentAPIError;
  }
  return (await response.json()) as T;
}

export function getAgentRuns(filters: { agent?: string; status?: AgentRunStatus } = {}) {
  const query = new URLSearchParams({ limit: "200" });
  if (filters.agent) query.set("agent_name", filters.agent);
  if (filters.status) query.set("status", filters.status);
  return request<AgentRunSummary[]>(`/runs?${query}`);
}

export function getAgentRun(traceId: string) {
  return request<AgentRunDetail>(`/runs/${encodeURIComponent(traceId)}`);
}

async function parseAskError(response: Response): Promise<AgentAPIError> {
  const error: AgentAPIError = { message: askFallbackMessage(response.status), status: response.status };
  try {
    const payload = (await response.json()) as Record<string, unknown>;
    if (typeof payload.detail === "string") error.message = payload.detail;
  } catch {
    // Keep the status-based fallback for HTML or malformed upstream bodies.
  }
  return error;
}

/**
 * Ask one question through the LangGraph agent, which classifies and routes it to the knowledge
 * base, the live ticket-status tool, or both, applies guardrails, and records a trace.
 */
export async function askAgent(question: string): Promise<AgentAnswer> {
  const response = await fetchWithAuth(`${API_PATH}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ question }),
    cache: "no-store",
  });
  if (!response.ok) throw await parseAskError(response);
  return (await response.json()) as AgentAnswer;
}
