"use client";

import { BarChart3, PackagePlus, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { RangeControls } from "./RangeControls";
import { TelemetryPageHeader } from "./TelemetryPageHeader";
import { StatCard } from "@/components/StatCard";
import { defaultRange, getDispatchMetrics, getReceivingMetrics, telemetryError } from "@/lib/telemetry/api";
import type { DateRange, DispatchMetrics, ReceivingMetrics } from "@/lib/telemetry/types";

export function FulfilmentView() {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [dispatch, setDispatch] = useState<DispatchMetrics | null>(null);
  const [receiving, setReceiving] = useState<ReceivingMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getDispatchMetrics(range), getReceivingMetrics(range)])
      .then(([dispatchResult, receivingResult]) => {
        if (!active) return;
        setDispatch(dispatchResult);
        setReceiving(receivingResult);
      })
      .catch((caught) => active && setError(telemetryError(caught).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [range]);

  function applyRange(next: DateRange) {
    setLoading(true);
    setError("");
    setRange(next);
  }

  const totalDispatched = dispatch?.rows.reduce((sum, row) => sum + row.dispatched, 0) ?? 0;
  const totalRejected = dispatch?.rows.reduce((sum, row) => sum + row.rejected, 0) ?? 0;
  const totalReceived = receiving?.rows.reduce((sum, row) => sum + row.count, 0) ?? 0;

  return (
    <section className="mx-auto w-full max-w-7xl">
      <TelemetryPageHeader
        eyebrow="Telemetry"
        title="Fulfilment"
        description="Exact dispatch and receiving volume per warehouse (LA / ZGZ), from the inventory system of record. Rejected-dispatch counts are best-effort diagnostics and may undercount."
      />
      <RangeControls value={range} onApply={applyRange} />

      {error ? (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {loading ? <p className="text-sm text-neutral-600">Loading fulfilment telemetry…</p> : null}

      {!loading && !error && dispatch && receiving ? (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              label="Dispatched (exact)"
              value={String(totalDispatched)}
              detail="Committed dispatch movements in range"
              icon={<BarChart3 className="h-4 w-4" aria-hidden="true" />}
            />
            <StatCard
              label="Rejected (diagnostic)"
              value={String(totalRejected)}
              detail="Best-effort — may undercount on restart"
              icon={<TriangleAlert className="h-4 w-4" aria-hidden="true" />}
            />
            <StatCard
              label="Received (exact)"
              value={String(totalReceived)}
              detail="Committed receiving movements in range"
              icon={<PackagePlus className="h-4 w-4" aria-hidden="true" />}
            />
          </div>

          <div>
            <h2 className="mb-2 text-lg font-black text-navy-deep">Dispatch by day and warehouse</h2>
            <p className="mb-3 text-xs text-neutral-500">
              <span className="font-black uppercase tracking-wide text-coral">Diagnostic</span> columns
              (rejected, indicative failure rate) are best-effort and are not exact KPIs.
            </p>
            <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                  <tr>
                    <th className="px-4 py-3">Date (UTC)</th>
                    <th className="px-4 py-3">Warehouse</th>
                    <th className="px-4 py-3">Dispatched</th>
                    <th className="px-4 py-3">Rejected*</th>
                    <th className="px-4 py-3">Indicative failure rate*</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-mist">
                  {dispatch.rows.map((row) => (
                    <tr key={`${row.date}-${row.warehouse}`}>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.date}</td>
                      <td className="px-4 py-3 font-bold text-navy">{row.warehouse}</td>
                      <td className="px-4 py-3 tabular-nums text-navy-deep">{row.dispatched}</td>
                      <td className="px-4 py-3 tabular-nums text-neutral-700">{row.rejected}</td>
                      <td className="px-4 py-3 tabular-nums text-neutral-700">
                        {(row.indicative_failure_rate * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!dispatch.rows.length ? (
                <p className="p-6 text-sm text-neutral-600">No dispatch telemetry in this range.</p>
              ) : null}
            </div>
            <p className="mt-2 text-xs text-neutral-500">* Best-effort diagnostic — may undercount.</p>
          </div>

          <div>
            <h2 className="mb-3 text-lg font-black text-navy-deep">Receiving by day and warehouse</h2>
            <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                  <tr>
                    <th className="px-4 py-3">Date (UTC)</th>
                    <th className="px-4 py-3">Warehouse</th>
                    <th className="px-4 py-3">Received</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-mist">
                  {receiving.rows.map((row) => (
                    <tr key={`${row.date}-${row.warehouse}`}>
                      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{row.date}</td>
                      <td className="px-4 py-3 font-bold text-navy">{row.warehouse}</td>
                      <td className="px-4 py-3 tabular-nums text-navy-deep">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!receiving.rows.length ? (
                <p className="p-6 text-sm text-neutral-600">No receiving telemetry in this range.</p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
