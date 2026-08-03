import { fetchWithAuth } from "@/lib/auth/client-http";
import type { KnowledgeAPIError, KnowledgeAnswer } from "@/lib/knowledge/types";

const API_PATH = "/api/knowledge";

function fallbackMessage(status: number) {
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 422) return "Please enter a question.";
  if (status === 502) return "The knowledge assistant is temporarily unavailable.";
  if (status === 503) return "The knowledge base is not available right now.";
  if (status === 504) return "The knowledge assistant timed out. Please try again.";
  return `The knowledge assistant failed with status ${status}.`;
}

export function knowledgeError(error: unknown): KnowledgeAPIError {
  if (error && typeof error === "object" && "message" in error && "status" in error) {
    return error as KnowledgeAPIError;
  }
  return { message: "Something went wrong. Please try again.", status: 0 };
}

async function parseError(response: Response): Promise<KnowledgeAPIError> {
  const error: KnowledgeAPIError = { message: fallbackMessage(response.status), status: response.status };
  try {
    const payload = (await response.json()) as Record<string, unknown>;
    if (typeof payload.detail === "string") error.message = payload.detail;
  } catch {
    // Keep the status-based fallback for HTML or malformed upstream bodies.
  }
  return error;
}

export async function askKnowledge(question: string): Promise<KnowledgeAnswer> {
  const response = await fetchWithAuth(`${API_PATH}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ question }),
    cache: "no-store",
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as KnowledgeAnswer;
}
