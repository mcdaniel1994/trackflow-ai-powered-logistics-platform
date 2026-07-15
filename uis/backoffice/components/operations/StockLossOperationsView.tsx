"use client";

import { PackageMinus } from "lucide-react";
import { useState } from "react";
import { OperationsPageHeader } from "./OperationsPageHeader";
import { StatCard } from "@/components/StatCard";
import { LiveIndicator } from "@/components/telemetry/LiveIndicator";
import { RangeControls } from "@/components/telemetry/RangeControls";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";
import { defaultRange, getStockLossMetrics, telemetryError } from "@/lib/telemetry/api";
import type { DateRange, StockLossMetrics } from "@/lib/telemetry/types";

export function StockLossOperationsView() {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const { data, error, loading, lastUpdated } = useAutoRefresh<StockLossMetrics>(
    () => getStockLossMetrics(range),
    [range],
    { mapError: (caught) => telemetryError(caught).message },
  );
  const totalLossUnits = data?.rows.reduce((sum, row) => sum + row.units, 0) ?? 0;

  return (
    <section className="mx-auto w-full max-w-7xl">
      <OperationsPageHeader title="Stock loss" description="Exact confirmed stock-loss events and units per warehouse, read from the inventory system of record." />
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <RangeControls value={range} onApply={setRange} />
        <LiveIndicator lastUpdated={lastUpdated} />
      </div>
      {error ? <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
      {loading ? <p className="text-sm text-neutral-600">Loading stock-loss metrics…</p> : null}
      {!loading && !error && data ? (
        <div className="space-y-8">
          <div className="max-w-md">
            <StatCard label="Stock loss units (exact)" value={String(totalLossUnits)} detail="Units written off as loss in range" icon={<PackageMinus className="h-4 w-4" aria-hidden="true" />} />
          </div>
          <div>
            <h2 className="mb-3 text-lg font-black text-navy-deep">Stock loss by day and warehouse</h2>
            <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600"><tr><th className="px-4 py-3">Date (UTC)</th><th className="px-4 py-3">Warehouse</th><th className="px-4 py-3">Events</th><th className="px-4 py-3">Units</th></tr></thead>
                <tbody className="divide-y divide-mist">{data.rows.map((row) => <tr key={`${row.date}-${row.warehouse}`}><td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.date}</td><td className="px-4 py-3 font-bold text-navy">{row.warehouse}</td><td className="px-4 py-3 tabular-nums text-neutral-700">{row.count}</td><td className="px-4 py-3 tabular-nums text-navy-deep">{row.units}</td></tr>)}</tbody>
              </table>
              {!data.rows.length ? <p className="p-6 text-sm text-neutral-600">No stock-loss movements in this range.</p> : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
