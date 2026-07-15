"use client";

import { BarChart3, CalendarClock, CircleCheck, Play, RefreshCw, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { LiveIndicator } from "@/components/telemetry/LiveIndicator";
import { useAuth } from "@/lib/auth/context";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";
import {
  getPipelineRunsStatus,
  getWeeklyPerformance,
  reportingError,
  requestPipelineRun,
} from "@/lib/reporting/api";
import type {
  PipelineRunsStatus,
  ReportWarehouse,
  WeeklyPerformanceEntry,
  WeeklyPerformanceReport,
} from "@/lib/reporting/types";

const WAREHOUSES: Array<{ id: ReportWarehouse; label: string }> = [
  { id: "los_angeles", label: "Los Angeles" },
  { id: "zaragoza", label: "Zaragoza" },
];

function isMonday(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.getUTCDay() === 1;
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "Not yet available";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Chicago",
  }).format(new Date(value));
}

function statusTone(status: string) {
  if (status === "idle") return "border-teal/50 bg-teal/10 text-navy";
  if (status === "stuck" || status === "unavailable") return "border-rose-200 bg-rose-50 text-rose-800";
  if (status === "processing") return "border-sky/50 bg-sky/10 text-navy";
  return "border-coral/40 bg-coral/10 text-navy";
}

function queueStateMessage(status: PipelineRunsStatus) {
  if (status.queue_state === "processing") return "A reporting run is processing.";
  if (status.queue_state === "queued") return "Queued work is waiting behind the current run.";
  if (status.queue_state === "retrying") {
    return `Retrying — attempt ${status.latest?.attempt ?? 1} of 5, next try at ${formatTimestamp(status.latest?.next_attempt_at)}.`;
  }
  if (status.queue_state === "unavailable") {
    return "Reporting worker or orchestrator is not responding; queued work will wait.";
  }
  if (status.queue_state === "stuck") {
    return "Reporting worker is running but not making progress — see the reporting runbook.";
  }
  return "Reporting is idle and ready for work.";
}

function ReportTable({ label, rows }: { label: string; rows: WeeklyPerformanceEntry[] }) {
  return (
    <section aria-labelledby={`warehouse-${label.toLowerCase().replaceAll(" ", "-")}`}>
      <h2 id={`warehouse-${label.toLowerCase().replaceAll(" ", "-")}`} className="mb-3 text-xl font-black text-navy-deep">
        {label}
      </h2>
      <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
            <tr>
              <th className="px-4 py-3">Client</th>
              <th className="px-4 py-3">Inbound units</th>
              <th className="px-4 py-3">Outbound orders</th>
              <th className="px-4 py-3">Stockout events</th>
              <th className="px-4 py-3">Discrepancy events</th>
              <th className="px-4 py-3">Discrepancy rate</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-mist">
            {rows.map((entry) => (
              <tr key={entry.client_id}>
                <td className="px-4 py-3 font-black text-navy-deep" title={`Client ID: ${entry.client_id}`}>
                  {entry.client_name}
                </td>
                <td className="px-4 py-3 tabular-nums">{entry.inbound_units_count.toLocaleString()}</td>
                <td className="px-4 py-3 tabular-nums">{entry.outbound_orders_count.toLocaleString()}</td>
                <td className="px-4 py-3 tabular-nums">{entry.stockout_events_count.toLocaleString()}</td>
                <td className="px-4 py-3 tabular-nums">{entry.discrepancy_events_count.toLocaleString()}</td>
                <td className="px-4 py-3 tabular-nums">{(entry.discrepancy_rate * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <p className="p-6 text-sm text-neutral-600">No client activity for this warehouse.</p> : null}
      </div>
    </section>
  );
}

function PipelineStatusStrip({ status, now }: { status: PipelineRunsStatus; now: number | null }) {
  const latest = status.latest;
  const successful = status.latest_successful;
  const stale = successful && now ? now - new Date(successful.finished_at).getTime() > 26 * 60 * 60 * 1000 : false;

  return (
    <section className="grid gap-3 rounded-xl border border-mist bg-white p-4 shadow-sm md:grid-cols-3" aria-label="Pipeline status">
      <div>
        <p className="text-xs font-black uppercase tracking-wide text-neutral-500">Current run</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-xs font-black uppercase ${statusTone(status.queue_state)}`}>
            {status.queue_state}
          </span>
          {latest ? <span className="text-xs font-bold text-neutral-600">{latest.trigger_type}</span> : null}
          {status.queued.length ? (
            <span className="rounded-full border border-coral/40 bg-coral/10 px-2.5 py-1 text-xs font-black text-navy">
              {status.queued.length} queued
            </span>
          ) : null}
        </div>
        {latest?.status === "failed" && latest.error_code ? (
          <p role="alert" className="mt-2 text-xs font-bold text-rose-700">Failure: {latest.error_code}</p>
        ) : null}
        <p
          role={status.queue_state === "stuck" || status.queue_state === "unavailable" ? "alert" : undefined}
          className={`mt-2 text-xs font-bold ${status.queue_state === "stuck" || status.queue_state === "unavailable" ? "text-rose-700" : "text-neutral-600"}`}
        >
          {queueStateMessage(status)}
        </p>
      </div>
      <div>
        <p className="text-xs font-black uppercase tracking-wide text-neutral-500">Last successful refresh</p>
        <p className="mt-2 text-sm font-black text-navy-deep">{formatTimestamp(successful?.finished_at)}</p>
        {stale ? <p className="mt-1 text-xs font-bold text-coral">Stale — the daily refresh may have been missed.</p> : null}
      </div>
      <div>
        <p className="text-xs font-black uppercase tracking-wide text-neutral-500">Next scheduled refresh</p>
        <p className="mt-2 text-sm font-black text-navy-deep">7:00 AM (America/Chicago)</p>
        <p className="mt-1 text-xs text-neutral-600">{formatTimestamp(status.next_scheduled_refresh.next_occurrence_utc)}</p>
      </div>
    </section>
  );
}

export function BusinessReportingView() {
  const { user } = useAuth();
  const [selectedWeek, setSelectedWeek] = useState("");
  const [draftWeek, setDraftWeek] = useState("");
  const [weekError, setWeekError] = useState("");
  const [runMessage, setRunMessage] = useState("");
  const [runError, setRunError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, error, loading, lastUpdated } = useAutoRefresh<{
    report: WeeklyPerformanceReport;
    status: PipelineRunsStatus;
  }>(
    () => Promise.all([getWeeklyPerformance(selectedWeek || undefined), getPipelineRunsStatus()]).then(
      ([report, status]) => ({ report, status }),
    ),
    [selectedWeek, refreshKey],
    { mapError: (caught) => reportingError(caught).message },
  );

  function applyWeek() {
    const nextWeek = draftWeek || data?.report.week_start || "";
    if (!isMonday(nextWeek)) {
      setWeekError("Choose a Monday to load an ISO reporting week.");
      return;
    }
    setWeekError("");
    setSelectedWeek(nextWeek);
  }

  async function trigger(forceRefresh: boolean) {
    const explanation = forceRefresh
      ? "Force refresh creates distinct work and recomputes directly from source records. Continue?"
      : "Run now queues a durable refresh. An identical pending request may be reused. Continue?";
    if (!window.confirm(explanation)) return;
    setSubmitting(true);
    setRunError("");
    setRunMessage("");
    try {
      const accepted = await requestPipelineRun({
        ...(selectedWeek ? { week_start: selectedWeek } : {}),
        force_refresh: forceRefresh,
      });
      setRunMessage(`Run ${accepted.run_id} queued.`);
      setRefreshKey((value) => value + 1);
    } catch (caught) {
      setRunError(reportingError(caught).message);
    } finally {
      setSubmitting(false);
    }
  }

  const report = data?.report ?? null;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Business reporting</p>
            <h1 className="mt-2 text-3xl font-black text-navy-deep">Weekly warehouse and client performance</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-600">
              Verified weekly KPIs from TrackFlow&apos;s durable inventory and business-event records.
            </p>
          </div>
          <LiveIndicator lastUpdated={lastUpdated} />
        </div>
      </header>

      <div className="flex flex-wrap items-end justify-between gap-4 rounded-xl border border-mist bg-ivory/60 p-4">
        <div>
          <label htmlFor="report-week" className="block text-xs font-black uppercase tracking-wide text-neutral-600">Report week (Monday)</label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input id="report-week" type="date" value={draftWeek || report?.week_start || ""} onChange={(event) => setDraftWeek(event.target.value)} className="rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy" />
            <button type="button" onClick={applyWeek} className="rounded-lg border border-navy bg-navy px-4 py-2 text-sm font-black text-white">Load week</button>
          </div>
          {weekError ? <p role="alert" className="mt-2 text-xs font-bold text-rose-700">{weekError}</p> : null}
        </div>
        {user.role === "admin" ? (
          <div className="flex flex-wrap gap-2" aria-label="Administrator reporting controls">
            <button type="button" disabled={submitting} onClick={() => void trigger(false)} className="inline-flex items-center gap-2 rounded-lg border border-navy bg-white px-4 py-2 text-sm font-black text-navy disabled:opacity-50">
              <Play className="h-4 w-4" aria-hidden="true" /> Run now
            </button>
            <button type="button" disabled={submitting} onClick={() => void trigger(true)} className="inline-flex items-center gap-2 rounded-lg border border-coral bg-coral px-4 py-2 text-sm font-black text-white disabled:opacity-50">
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> Force refresh
            </button>
          </div>
        ) : null}
      </div>

      {runMessage ? <p role="status" className="rounded-lg border border-teal/40 bg-teal/10 p-3 text-sm font-bold text-navy">{runMessage}</p> : null}
      {runError ? <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{runError}</p> : null}
      {error ? <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
      {loading ? <p className="text-sm text-neutral-600">Loading business reporting…</p> : null}

      {data ? <PipelineStatusStrip status={data.status} now={lastUpdated} /> : null}

      {report?.week_start ? (
        <section className="rounded-xl border border-mist bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-3">
            <CalendarClock className="h-5 w-5 text-sky" aria-hidden="true" />
            <div>
              <p className="text-xs font-black uppercase tracking-wide text-neutral-500">Report period</p>
              <p className="font-black text-navy-deep">Week of {report.week_start}</p>
            </div>
            {report.incomplete ? (
              <span className="ml-auto inline-flex items-center gap-2 rounded-full border border-coral bg-coral/10 px-3 py-1.5 text-xs font-black text-navy">
                <TriangleAlert className="h-4 w-4 text-coral" aria-hidden="true" /> Incomplete — ledger reset mid-week
              </span>
            ) : (
              <span className="ml-auto inline-flex items-center gap-2 rounded-full border border-teal/50 bg-teal/10 px-3 py-1.5 text-xs font-black text-navy">
                <CircleCheck className="h-4 w-4 text-teal" aria-hidden="true" /> Verified
              </span>
            )}
          </div>
        </section>
      ) : null}

      {report && !report.entries.length ? (
        <div className="rounded-xl border border-dashed border-mist bg-white p-8 text-center">
          <BarChart3 className="mx-auto h-8 w-8 text-sky" aria-hidden="true" />
          <p className="mt-3 font-black text-navy-deep">No report computed yet for this week</p>
        </div>
      ) : null}

      {report?.entries.length ? (
        <div className="space-y-8">
          {WAREHOUSES.map((warehouse) => (
            <ReportTable key={warehouse.id} label={warehouse.label} rows={report.entries.filter((entry) => entry.warehouse === warehouse.id)} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
