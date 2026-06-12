import type { IncidentAnalysisResult } from "./incident-types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

// Base-URL precedence: the dedicated incident-processor var wins, then the
// generic shared-backend var, then localhost for local dev. The talent client
// (lib/talent/api.ts) deliberately uses NEXT_PUBLIC_TALENT_API_URL instead so
// the two features never end up pointed at each other's backend.
function getApiBaseUrl() {
  const configured =
    process.env.NEXT_PUBLIC_INCIDENT_PROCESSOR_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    DEFAULT_API_BASE_URL;

  return configured.replace(/\/$/, "");
}

async function readSafeError(response: Response) {
  try {
    const payload = await response.json();
    const code = payload?.detail?.code ?? "REQUEST_FAILED";
    return `Incident processor request failed: ${code}`;
  } catch {
    return `Incident processor request failed: ${response.status}`;
  }
}

export async function analyzeIncidentCsv(file: File): Promise<IncidentAnalysisResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getApiBaseUrl()}/api/incidents/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readSafeError(response));
  }

  return response.json() as Promise<IncidentAnalysisResult>;
}

export function getIncidentExportUrl() {
  return `${getApiBaseUrl()}/api/incidents/results/export`;
}

