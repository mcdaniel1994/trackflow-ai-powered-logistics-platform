// The ONLY file in the app that calls `fetch`. Every component reaches the API
// through one of the exported functions below.
//
// Why a single chokepoint:
//   - one place for the base URL, headers, error parsing, and JSON normalization
//   - components stay focused on UI and never touch HTTP details
//   - swapping the backend (real API, mock, recorded fixtures) only touches this file
//
// Layout:
//   1. Types: Raw* shapes describe what the server actually returns; Candidate/Note
//      are the clean shapes the rest of the app uses.
//   2. Normalizers: convert Raw -> clean (handles null fields, alternate field names).
//   3. `request()`: shared fetch wrapper — headers, error parsing, no-store cache.
//   4. Exported endpoint functions: thin wrappers around `request()`.

import type {
  APIError,
  Candidate,
  CandidateCreate,
  CandidatePatch,
  Note,
  Stage,
  Status,
} from "@/lib/talent/types";

// The mock API uses `applied_at` in some responses and `application_date` in others,
// and can return `null` for optional URL fields. The normalizer below hides this.
type RawCandidate = Omit<Candidate, "application_date" | "linkedin_url" | "cv_url"> & {
  applied_at?: string;
  application_date?: string;
  linkedin_url: string | null;
  cv_url: string | null;
};

type RawNote = Note & {
  record_id?: string;
};

// Most list endpoints wrap the array in `{ data: [...] }`. This generic models that.
type ListResponse<T> = {
  data?: T[];
  total?: number;
  page?: number;
  limit?: number;
  meta?: {
    total?: number;
  };
};

// We extend APIError with `status` so callers can branch on 404 vs anything else.
// `isNotFoundError` below uses this to render the friendly NotFound page.
type ThrownAPIError = APIError & {
  status?: number;
};

// `NEXT_PUBLIC_` prefix is required for env vars that need to reach the browser.
// We strip a trailing slash so endpoint paths can start with `/records` cleanly.
// This client uses its own NEXT_PUBLIC_TALENT_API_URL var: the backoffice's
// incident client (lib/incident-api.ts) falls back to NEXT_PUBLIC_API_URL, so
// sharing that name would point the talent tracker at the wrong backend.
const FALLBACK_API_URL = "https://playground.4geeks.com/tracker/api/v1";
const API_URL = (process.env.NEXT_PUBLIC_TALENT_API_URL ?? FALLBACK_API_URL).replace(/\/$/, "");

// Squashes server quirks so the rest of the app sees one clean shape:
//   - `null` LinkedIn/CV URLs become empty strings (simpler to render).
//   - `applied_at` is treated as a synonym for `application_date`.
function normalizeCandidate(raw: RawCandidate): Candidate {
  return {
    id: raw.id,
    full_name: raw.full_name,
    email: raw.email,
    phone: raw.phone,
    position: raw.position,
    linkedin_url: raw.linkedin_url ?? "",
    cv_url: raw.cv_url ?? "",
    experience_years: raw.experience_years,
    status: raw.status,
    stage: raw.stage,
    application_date: raw.application_date ?? raw.applied_at ?? "",
  };
}

function normalizeNote(raw: RawNote): Note {
  return {
    id: raw.id,
    content: raw.content,
    created_at: raw.created_at,
  };
}

// Inverse of `normalizeCandidate` for outgoing requests:
//   - strip `id` (server owns it)
//   - rename our clean `application_date` back to the API's `applied_at`
function toApiPayload(body: CandidateCreate | CandidatePatch) {
  const payload = { ...body } as CandidatePatch;
  delete payload.id;
  const { application_date, ...rest } = payload;
  return {
    ...rest,
    ...(application_date ? { applied_at: application_date } : {}),
  };
}

// When the API reports a validation error on `applied_at`, surface it under the
// field name the form actually uses (`application_date`). Keeps error mapping
// invisible to the form layer.
function fieldNameFromApi(field: string) {
  return field === "applied_at" ? "application_date" : field;
}

// Defensive error parser: the API can return error info in several shapes
// (FastAPI `detail`, generic `message`, nested `error.message`). We accept any
// of them and fall back to a generic message so callers always get something
// useful to render — the spec rule is "never fail silently".
async function parseAPIError(response: Response): Promise<ThrownAPIError> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    payload = undefined;
  }

  const error: ThrownAPIError = {
    message: `Request failed with status ${response.status}.`,
    status: response.status,
  };

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;

    if (typeof record.message === "string") {
      error.message = record.message;
    }

    if (record.error && typeof record.error === "object") {
      const nested = record.error as Record<string, unknown>;
      if (typeof nested.message === "string") {
        error.message = nested.message;
      }
    }

    if (typeof record.detail === "string") {
      error.message = record.detail;
    }

    if (Array.isArray(record.detail)) {
      const fieldErrors: Record<string, string> = {};

      for (const item of record.detail) {
        if (!item || typeof item !== "object") {
          continue;
        }

        const detail = item as Record<string, unknown>;
        const message = typeof detail.msg === "string" ? detail.msg : error.message;
        const loc = Array.isArray(detail.loc) ? detail.loc : [];
        const field = loc.length ? String(loc[loc.length - 1]) : "";

        if (field) {
          fieldErrors[fieldNameFromApi(field)] = message;
        }
      }

      if (Object.keys(fieldErrors).length) {
        error.field_errors = fieldErrors;
        error.message = "Please review the highlighted fields.";
      }
    }
  }

  return error;
}

// Core fetch wrapper. Every endpoint function below routes through this.
//   - `cache: "no-store"` keeps server-rendered detail pages fresh on each request
//     (Next 15 caches fetches aggressively by default; this opts out).
//   - `Content-Type: application/json` is only set when there's a body to send.
//   - Non-2xx -> parse and throw a typed APIError (caught by callers as `unknown`,
//     handled via the `errorMessage` / `errorFieldErrors` helpers below).
//   - 204 No Content -> resolve with undefined (used by deleteNote).
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: init?.cache ?? "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw await parseAPIError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

// --- Error helpers ---------------------------------------------------------
// `try/catch` in components/pages catches `unknown`. These helpers safely pull
// the bits we care about (top-level message, per-field errors, 404 detection)
// without each call site having to repeat the same type-narrowing.

export function errorMessage(error: unknown) {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") {
      return message;
    }
  }

  return "Something went wrong. Please try again.";
}

export function errorFieldErrors(error: unknown) {
  if (error && typeof error === "object" && "field_errors" in error) {
    const fieldErrors = (error as { field_errors?: unknown }).field_errors;
    if (fieldErrors && typeof fieldErrors === "object") {
      return fieldErrors as Record<string, string>;
    }
  }

  return {};
}

export function isNotFoundError(error: unknown) {
  if (!error || typeof error !== "object") {
    return false;
  }

  const status = (error as ThrownAPIError).status;
  return status === 404 || status === 422;
}

// --- Endpoint functions ----------------------------------------------------
// Each function maps to one HTTP route. The names below are the public API of
// this module; components import only these (plus the error helpers above).

// One page of candidates plus the pagination facts the table footer needs.
// `total` is null when the API doesn't report one — callers degrade to
// Previous/Next based on the returned row count.
export type CandidatePage = {
  candidates: Candidate[];
  total: number | null;
  page: number;
  limit: number;
};

export async function getCandidates(params: {
  status?: Status;
  stage?: Stage;
  q?: string;
  page?: number;
  limit?: number;
}): Promise<CandidatePage> {
  const page = params.page && params.page > 0 ? params.page : 1;
  const limit = params.limit && params.limit > 0 ? params.limit : 20;

  const searchParams = new URLSearchParams();
  searchParams.set("page", String(page));
  searchParams.set("limit", String(limit));

  if (params.status) {
    searchParams.set("status", params.status);
  }

  if (params.stage) {
    searchParams.set("stage", params.stage);
  }

  if (params.q) {
    searchParams.set("search", params.q);
  }

  const response = await request<ListResponse<RawCandidate>>(`/records?${searchParams.toString()}`);
  return {
    candidates: (response.data ?? []).map(normalizeCandidate),
    total: response.total ?? response.meta?.total ?? null,
    page: response.page ?? page,
    limit: response.limit ?? limit,
  };
}

export async function getCandidate(id: string): Promise<Candidate> {
  const response = await request<RawCandidate>(`/records/${encodeURIComponent(id)}`);
  return normalizeCandidate(response);
}

export async function createCandidate(body: CandidateCreate): Promise<Candidate> {
  const response = await request<RawCandidate>("/records", {
    method: "POST",
    body: JSON.stringify(toApiPayload(body)),
  });

  return normalizeCandidate(response);
}

// PATCH (not PUT): only the changed fields are sent. This is what powers the
// inline status/stage selects on the detail page — one field at a time.
export async function patchCandidate(id: string, body: CandidatePatch): Promise<Candidate> {
  const response = await request<RawCandidate>(`/records/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(toApiPayload(body)),
  });

  return normalizeCandidate(response);
}

export async function getNotes(id: string): Promise<Note[]> {
  const response = await request<ListResponse<RawNote>>(
    `/records/${encodeURIComponent(id)}/notes`,
  );

  return (response.data ?? []).map(normalizeNote);
}

export async function createNote(id: string, content: string): Promise<Note> {
  const response = await request<RawNote>(`/records/${encodeURIComponent(id)}/notes`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });

  return normalizeNote(response);
}

export async function deleteNote(id: string, noteId: string): Promise<void> {
  await request<void>(
    `/records/${encodeURIComponent(id)}/notes/${encodeURIComponent(noteId)}`,
    {
      method: "DELETE",
    },
  );
}
