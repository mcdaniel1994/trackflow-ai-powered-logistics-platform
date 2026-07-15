"use client";

import { TriangleAlert } from "lucide-react";
import { useState } from "react";
import { LiveIndicator } from "./LiveIndicator";
import { RangeControls } from "./RangeControls";
import { TelemetryPageHeader } from "./TelemetryPageHeader";
import { StatCard } from "@/components/StatCard";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";
import { defaultRange, getDispatchMetrics, telemetryError } from "@/lib/telemetry/api";
import type { DateRange, DispatchMetrics } from "@/lib/telemetry/types";

export function FulfilmentView() {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const { data: dispatch, error, loading, lastUpdated } = useAutoRefresh<DispatchMetrics>(
    () => getDispatchMetrics(range),
    [range],
    { mapError: (caught) => telemetryError(caught).message },
  );

  function applyRange(next: DateRange) {
    setRange(next);
  }

  const totalRejected = dispatch?.rows.reduce((sum, row) => sum + row.rejected, 0) ?? 0;

  return (
    <section className="mx-auto w-full max-w-7xl">
      <TelemetryPageHeader
        eyebrow="Technical telemetry"
        title="Dispatch diagnostics"
        description="Best-effort rejected-dispatch signals for technical diagnosis. These figures may undercount and are not business KPIs."
      />
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <RangeControls value={range} onApply={applyRange} />
        <LiveIndicator lastUpdated={lastUpdated} />
      </div>

      {error ? (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {loading ? <p className="text-sm text-neutral-600">Loading dispatch diagnostics…</p> : null}

      {!loading && !error && dispatch ? (
        <div className="space-y-8">
          <div className="max-w-md">
            <StatCard
              label="Rejected (diagnostic)"
              value={String(totalRejected)}
              detail="Best-effort — may undercount on restart"
              icon={<TriangleAlert className="h-4 w-4" aria-hidden="true" />}
            />
          </div>

          <div>
            <h2 className="mb-2 text-lg font-black text-navy-deep">Rejected dispatches by day and warehouse</h2>
            <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                  <tr>
                    <th className="px-4 py-3">Date (UTC)</th>
                    <th className="px-4 py-3">Warehouse</th>
                    <th className="px-4 py-3">Rejected*</th>
                    <th className="px-4 py-3">Indicative failure rate*</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-mist">
                  {dispatch.rows.map((row) => (
                    <tr key={`${row.date}-${row.warehouse}`}>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.date}</td>
                      <td className="px-4 py-3 font-bold text-navy">{row.warehouse}</td>
                      <td className="px-4 py-3 tabular-nums text-neutral-700">{row.rejected}</td>
                      <td className="px-4 py-3 tabular-nums text-neutral-700">
                        {(row.indicative_failure_rate * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!dispatch.rows.length ? (
                <p className="p-6 text-sm text-neutral-600">No rejected-dispatch diagnostics in this range.</p>
              ) : null}
            </div>
            <p className="mt-2 text-xs text-neutral-500">* Best-effort diagnostic — may undercount.</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
