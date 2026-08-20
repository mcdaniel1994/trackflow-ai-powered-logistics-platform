import { ArrowDownToLine, PackageCheck, ShoppingCart, TriangleAlert } from "lucide-react";
import type { WeeklyPerformanceEntry } from "@/lib/reporting/types";

type Tile = { label: string; value: number; icon: typeof ArrowDownToLine };

// KPI totals for the selected week. A single number is the right form here — never a one-value chart.
export function KpiTiles({ entries }: { entries: WeeklyPerformanceEntry[] }) {
  const sum = (key: keyof WeeklyPerformanceEntry) =>
    entries.reduce((total, entry) => total + (Number(entry[key]) || 0), 0);

  const tiles: Tile[] = [
    { label: "Inbound units", value: sum("inbound_units_count"), icon: ArrowDownToLine },
    { label: "Outbound orders", value: sum("outbound_orders_count"), icon: ShoppingCart },
    { label: "Stockout events", value: sum("stockout_events_count"), icon: PackageCheck },
    { label: "Discrepancy events", value: sum("discrepancy_events_count"), icon: TriangleAlert },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className="rounded-xl border border-mist bg-white p-4 shadow-sm dark:border-ink-600 dark:bg-ink-800"
        >
          <dt className="flex items-center gap-2 text-xs font-black uppercase tracking-wide text-neutral-500 dark:text-neutral-300">
            <tile.icon className="h-4 w-4 text-sky" aria-hidden="true" />
            {tile.label}
          </dt>
          <dd className="mt-2 text-2xl font-black tabular-nums text-navy-deep dark:text-neutral-100">
            {tile.value.toLocaleString()}
          </dd>
        </div>
      ))}
    </dl>
  );
}
