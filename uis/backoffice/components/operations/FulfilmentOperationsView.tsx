"use client";

import { BarChart3, PackagePlus } from "lucide-react";
import { useState } from "react";
import { OperationsPageHeader } from "./OperationsPageHeader";
import { StatCard } from "@/components/StatCard";
import { ResourceLiveIndicator, ResourceNotice } from "@/components/telemetry/ResourceStatus";
import { RangeControls } from "@/components/telemetry/RangeControls";
import { useResourcePolling } from "@/lib/hooks/useResourcePolling";
import { defaultRange, getDispatchMetrics, getReceivingMetrics, telemetryError } from "@/lib/telemetry/api";
import type { DateRange } from "@/lib/telemetry/types";

export function FulfilmentOperationsView() {
  const [range, setRange] = useState<DateRange>(defaultRange);
  const scope = `${range.from}:${range.to}`;
  const dispatch = useResourcePolling((signal) => getDispatchMetrics(range, signal), scope, (error) => telemetryError(error).message);
  const receiving = useResourcePolling((signal) => getReceivingMetrics(range, signal), scope, (error) => telemetryError(error).message);
  const totalDispatched = dispatch.data?.rows.reduce((sum, row) => sum + row.dispatched, 0);
  const totalReceived = receiving.data?.rows.reduce((sum, row) => sum + row.count, 0);

  return (
    <section className="mx-auto w-full max-w-7xl">
      <OperationsPageHeader
        title="Fulfilment"
        description="Exact committed dispatch and receiving volumes per warehouse, read from the inventory system of record."
      />
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <RangeControls value={range} onApply={setRange} />
        <ResourceLiveIndicator resources={[dispatch, receiving]} />
      </div>

      <div className="space-y-8">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <StatCard label="Dispatched (exact)" value={totalDispatched === undefined ? "—" : String(totalDispatched)} detail="Committed dispatch movements in range" icon={<BarChart3 className="h-4 w-4" aria-hidden="true" />} />
            <ResourceNotice resource={dispatch} label="Dispatch" />
          </div>
          <div>
            <StatCard label="Received (exact)" value={totalReceived === undefined ? "—" : String(totalReceived)} detail="Committed receiving movements in range" icon={<PackagePlus className="h-4 w-4" aria-hidden="true" />} />
            <ResourceNotice resource={receiving} label="Receiving" />
          </div>
        </div>

        <section aria-label="Dispatch details">
          {dispatch.data ? (
            <MetricTable
              title="Dispatch by day and warehouse"
              empty="No dispatch movements in this range."
              headings={["Date (UTC)", "Warehouse", "Dispatched"]}
              rows={dispatch.data.rows.map((row) => [row.date, row.warehouse, String(row.dispatched)])}
            />
          ) : null}
        </section>
        <section aria-label="Receiving details">
          {receiving.data ? (
            <MetricTable
              title="Receiving by day and warehouse"
              empty="No receiving movements in this range."
              headings={["Date (UTC)", "Warehouse", "Received"]}
              rows={receiving.data.rows.map((row) => [row.date, row.warehouse, String(row.count)])}
            />
          ) : null}
        </section>
      </div>
    </section>
  );
}

function MetricTable({ title, empty, headings, rows }: { title: string; empty: string; headings: string[]; rows: string[][] }) {
  return (
    <div>
      <h2 className="mb-3 text-lg font-black text-navy-deep">{title}</h2>
      <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600"><tr>{headings.map((heading) => <th key={heading} className="px-4 py-3">{heading}</th>)}</tr></thead>
          <tbody className="divide-y divide-mist">
            {rows.map((row) => <tr key={row.join("-")}>{row.map((cell, index) => <td key={`${index}-${cell}`} className={`px-4 py-3 ${index === 0 ? "font-mono text-xs text-neutral-600" : index === 1 ? "font-bold text-navy" : "tabular-nums text-navy-deep"}`}>{cell}</td>)}</tr>)}
          </tbody>
        </table>
        {!rows.length ? <p className="p-6 text-sm text-neutral-600">{empty}</p> : null}
      </div>
    </div>
  );
}
