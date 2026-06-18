import { statusLabel, statusTone } from "@/lib/suppliers/labels";
import type { Status } from "@/lib/suppliers/types";

type SupplierStatusBadgeProps = {
  status: Status;
};

const toneClasses = {
  green: "bg-green-100 text-green-800 border-green-200",
  coral: "bg-coral/15 text-navy-deep border-coral/30",
};

export function SupplierStatusBadge({ status }: SupplierStatusBadgeProps) {
  return (
    <span className={`inline-flex max-w-full justify-center rounded-md border px-2.5 py-1 text-center text-xs font-semibold leading-tight ${toneClasses[statusTone(status)]}`}>
      {statusLabel(status)}
    </span>
  );
}
