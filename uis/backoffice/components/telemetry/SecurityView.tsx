"use client";

import { PackageMinus, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { LiveIndicator } from "./LiveIndicator";
import { RangeControls } from "./RangeControls";
import { TelemetryPageHeader } from "./TelemetryPageHeader";
import { StatCard } from "@/components/StatCard";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";
import { defaultRange, getAccessDenialMetrics, getStockLossMetrics, telemetryError } from "@/lib/telemetry/api";
import type { AccessDenialMetrics, DateRange, StockLossMetrics } from "@/lib/telemetry/types";

const REASON_LABELS: Record<string, string> = {
  unauthenticated: "Unauthenticated",
  csrf: "CSRF rejected",
  password_change_required: "Password change required",
};

export function SecurityView() {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const { data, error, loading, lastUpdated } = useAutoRefresh<{
    denials: AccessDenialMetrics;
    loss: StockLossMetrics;
  }>(
    () =>
      Promise.all([getAccessDenialMetrics(range), getStockLossMetrics(range)]).then(([denials, loss]) => ({
        denials,
        loss,
      })),
    [range],
    { mapError: (caught) => telemetryError(caught).message },
  );

  const denials = data?.denials ?? null;
  const loss = data?.loss ?? null;

  function applyRange(next: DateRange) {
    setRange(next);
  }

  const totalDenials = denials?.rows.reduce((sum, row) => sum + row.count, 0) ?? 0;
  const totalLossUnits = loss?.rows.reduce((sum, row) => sum + row.units, 0) ?? 0;

  return (
    <section className="mx-auto w-full max-w-7xl">
      <TelemetryPageHeader
        eyebrow="Telemetry"
        title="Security"
        description="API access denials (best-effort) and confirmed stock loss per warehouse (exact). Login auditing is kept in Identity's safe logs in Phase 1 and is not shown here."
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
      {loading ? <p className="text-sm text-neutral-600">Loading security telemetry…</p> : null}

      {!loading && !error && denials && loss ? (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard
              label="Access denials (diagnostic)"
              value={String(totalDenials)}
              detail="Refused requests to protected APIs"
              icon={<ShieldAlert className="h-4 w-4" aria-hidden="true" />}
            />
            <StatCard
              label="Stock loss units (exact)"
              value={String(totalLossUnits)}
              detail="Units written off as loss in range"
              icon={<PackageMinus className="h-4 w-4" aria-hidden="true" />}
            />
          </div>

          <div>
            <h2 className="mb-3 text-lg font-black text-navy-deep">API access denials by day and reason</h2>
            <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                  <tr>
                    <th className="px-4 py-3">Date (UTC)</th>
                    <th className="px-4 py-3">Reason</th>
                    <th className="px-4 py-3">Count*</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-mist">
                  {denials.rows.map((row) => (
                    <tr key={`${row.date}-${row.reason}`}>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.date}</td>
                      <td className="px-4 py-3 font-bold text-navy">{REASON_LABELS[row.reason] ?? row.reason}</td>
                      <td className="px-4 py-3 tabular-nums text-neutral-700">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!denials.rows.length ? (
                <p className="p-6 text-sm text-neutral-600">No access-denial telemetry in this range.</p>
              ) : null}
            </div>
            <p className="mt-2 text-xs text-neutral-500">* Best-effort diagnostic — may undercount.</p>
          </div>

          <div>
            <h2 className="mb-3 text-lg font-black text-navy-deep">Stock loss by day and warehouse</h2>
            <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                  <tr>
                    <th className="px-4 py-3">Date (UTC)</th>
                    <th className="px-4 py-3">Warehouse</th>
                    <th className="px-4 py-3">Events</th>
                    <th className="px-4 py-3">Units</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-mist">
                  {loss.rows.map((row) => (
                    <tr key={`${row.date}-${row.warehouse}`}>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.date}</td>
                      <td className="px-4 py-3 font-bold text-navy">{row.warehouse}</td>
                      <td className="px-4 py-3 tabular-nums text-neutral-700">{row.count}</td>
                      <td className="px-4 py-3 tabular-nums text-navy-deep">{row.units}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!loss.rows.length ? (
                <p className="p-6 text-sm text-neutral-600">No stock-loss telemetry in this range.</p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
