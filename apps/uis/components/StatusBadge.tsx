// Two-step color pipeline:
//   Status value -> statusTone() returns a semantic tone name ("navy" | "coral" | ...)
//                -> toneClasses below maps the tone name to concrete Tailwind classes
//
// This lets callers pass just a Status and stay completely palette-agnostic. If
// the brand ever changes, only `toneClasses` needs updating.

import { statusLabel, statusTone } from "@/lib/labels";
import type { Status } from "@/lib/types";

type StatusBadgeProps = {
  status: Status;
};

const toneClasses = {
  navy: "bg-mist text-navy-deep border-neutral-200",
  coral: "bg-coral/15 text-navy-deep border-coral/30",
  green: "bg-green-100 text-green-800 border-green-200",
  muted: "bg-neutral-100 text-neutral-600 border-neutral-200",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold ${toneClasses[statusTone(status)]}`}
    >
      {statusLabel(status)}
    </span>
  );
}
