import type { IncidentAnalysisResult } from "./incident-types";
import { fetchWithAuth } from "@/lib/auth/client-http";

const API_PATH = "/api/incidents";

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

  const response = await fetchWithAuth(`${API_PATH}/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readSafeError(response));
  }

  return response.json() as Promise<IncidentAnalysisResult>;
}

export function getIncidentExportUrl() {
  return `${API_PATH}/results/export`;
}
