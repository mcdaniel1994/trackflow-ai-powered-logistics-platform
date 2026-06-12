// Single source of truth for converting raw API values into human-readable text
// and visual tones. Every badge, dropdown, and filter goes through this file.
//
// Why centralize: the spec rule "raw API values must never appear in the UI" is
// only enforceable if there's exactly one place that knows the mapping. If a new
// status is added on the backend, this is the only file that needs to change.

import type { Stage, Status } from "@/lib/talent/types";

// `Record<Status, string>` makes the compiler error if a new Status value gets
// added to the union in lib/types.ts but its label is forgotten here.
const statusLabels: Record<Status, string> = {
  received: "Received",
  in_progress: "In progress",
  selected: "Selected",
  discarded: "Discarded",
};

const stageLabels: Record<Stage, string> = {
  pending: "Pending review",
  review: "Under review",
  personal_interview: "Personal interview",
  technical_interview: "Technical interview",
  offer_presented: "Offer presented",
};

// "Tone" is the semantic color name (navy/coral/green/muted). StatusBadge.tsx
// maps each tone to a concrete Tailwind class set, so colors live in one place
// and code that uses them stays palette-agnostic.
const statusTones: Record<Status, "navy" | "coral" | "green" | "muted"> = {
  received: "navy",
  in_progress: "coral",
  selected: "green",
  discarded: "muted",
};

// `Object.keys` returns `string[]`; the `as Status[]` cast is safe here because
// the literal object is typed as `Record<Status, ...>`. Used to render the
// <option> list in filters and forms without hardcoding the order twice.
export const statusOptions = Object.keys(statusLabels) as Status[];
export const stageOptions = Object.keys(stageLabels) as Stage[];

// Type-guard pattern: when the predicate returns true, TypeScript narrows the
// input from `string | null` to the typed union. This lets us read `?status=foo`
// out of the URL and either accept it (typed) or fall back to "all".
export function isStatus(value: string | null | undefined): value is Status {
  return Boolean(value && value in statusLabels);
}

export function isStage(value: string | null | undefined): value is Stage {
  return Boolean(value && value in stageLabels);
}

export function statusLabel(status: Status) {
  return statusLabels[status];
}

export function stageLabel(stage: Stage) {
  return stageLabels[stage];
}

export function statusTone(status: Status) {
  return statusTones[status];
}
