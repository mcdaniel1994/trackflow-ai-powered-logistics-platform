"use client";

import { ShieldAlert } from "lucide-react";
import { useState } from "react";
import { LiveIndicator } from "./LiveIndicator";
import { RangeControls } from "./RangeControls";
import { TelemetryPageHeader } from "./TelemetryPageHeader";
import { StatCard } from "@/components/StatCard";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";
import { defaultRange, getAccessDenialMetrics, telemetryError } from "@/lib/telemetry/api";
import type { AccessDenialMetrics, DateRange } from "@/lib/telemetry/types";

const REASON_LABELS: Record<string, string> = {
  unauthenticated: "Unauthenticated",
  csrf: "CSRF rejected",
  password_change_required: "Password change required",
};

export function SecurityView() {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const { data: denials, error, loading, lastUpdated } = useAutoRefresh<AccessDenialMetrics>(
    () => getAccessDenialMetrics(range),
    [range],
    { mapError: (caught) => telemetryError(caught).message },
  );

  function applyRange(next: DateRange) {
    setRange(next);
  }

  const totalDenials = denials?.rows.reduce((sum, row) => sum + row.count, 0) ?? 0;

  return (
    <section className="mx-auto w-full max-w-7xl">
      <TelemetryPageHeader
        eyebrow="Technical telemetry"
        title="Security diagnostics"
        description="Best-effort API access-denial signals for technical diagnosis. Login auditing remains in Identity's safe logs and is not shown here."
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

      {!loading && !error && denials ? (
        <div className="space-y-8">
          <div className="max-w-md">
            <StatCard
              label="Access denials (diagnostic)"
              value={String(totalDenials)}
              detail="Refused requests to protected APIs"
              icon={<ShieldAlert className="h-4 w-4" aria-hidden="true" />}
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
        </div>
      ) : null}
    </section>
  );
}
