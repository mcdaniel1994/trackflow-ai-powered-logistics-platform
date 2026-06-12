// Stage is intentionally a single neutral chip — status carries the color signal,
// stage just says where in the funnel the candidate is. Keeps the table from
// looking like a Christmas tree when both badges sit side by side.

import { stageLabel } from "@/lib/talent/labels";
import type { Stage } from "@/lib/talent/types";

type StageBadgeProps = {
  stage: Stage;
};

export function StageBadge({ stage }: StageBadgeProps) {
  return (
    <span className="inline-flex rounded-md bg-mist px-2.5 py-1 text-xs font-semibold text-navy-deep">
      {stageLabel(stage)}
    </span>
  );
}
