// Domain types. These mirror the backend's shape exactly — field names match the API
// (snake_case, e.g. `full_name`) so the JSON payload maps 1:1 with no renaming.
//
// String-literal unions for Status/Stage give us two things for free:
//   1. The compiler rejects typos like "in_progres" anywhere in the codebase.
//   2. `isStatus()` / `isStage()` in lib/labels.ts can narrow `string` → typed union,
//      which lets us safely read filter values out of the URL.
//
// These raw values must never reach the UI — they only flow through lib/api.ts and
// get converted to display strings in lib/labels.ts. See spec § Labels.

export type Status = "received" | "in_progress" | "selected" | "discarded";

export type Stage =
  | "pending"
  | "review"
  | "personal_interview"
  | "technical_interview"
  | "offer_presented";

export interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string;
  cv_url: string;
  experience_years: number;
  status: Status;
  stage: Stage;
  application_date: string;
}

export interface Note {
  id: string;
  content: string;
  created_at: string;
}

// Partial<Candidate> = every field optional. Used by PATCH (only the changed fields go in the body).
export type CandidatePatch = Partial<Candidate>;

// Omit<Candidate, "id"> = same shape minus `id` (the server assigns the id on POST).
export type CandidateCreate = Omit<Candidate, "id">;

// What `lib/api.ts` throws on non-2xx responses. `field_errors` is keyed by form field
// name so CandidateForm can render the message next to the offending input.
export interface APIError {
  message: string;
  field_errors?: Record<string, string>;
}
