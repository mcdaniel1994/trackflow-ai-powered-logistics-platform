"use client";

import {
  AlertTriangle,
  Bot,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  Clock3,
  Coins,
  RefreshCw,
  Route,
  ShieldAlert,
  Wrench,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { agentError, getAgentRun, getAgentRuns } from "@/lib/agents/api";
import type { AgentRunDetail, AgentRunStatus, AgentRunSummary } from "@/lib/agents/types";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";

const STATUS_OPTIONS: { value: "" | AgentRunStatus; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "ok", label: "Succeeded" },
  { value: "rejected", label: "Rejected" },
  { value: "error", label: "Error" },
];

function label(value: string | null) {
  return (value || "—").replaceAll("_", " ").replaceAll(":", " · ");
}

function duration(value: number | null) {
  if (value === null) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)}s` : `${value}ms`;
}

const NOT_PRICED_HINT = "Token counts are exact, but this model has no published per-token price.";

// Distinguish "no data" (—) from "not priced" (tokens exist but the model is unpriced, e.g. deepseek-chat).
function costDisplay(value: number | null, tokens: number | null): { text: string; hint?: string } {
  if (value !== null) return { text: `$${value.toFixed(6)}` };
  if (tokens !== null && tokens > 0) return { text: "Not priced", hint: NOT_PRICED_HINT };
  return { text: "—" };
}

function when(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function StatusBadge({ status }: { status: string }) {
  const style =
    status === "ok"
      ? "bg-teal/15 text-teal-700 dark:text-teal"
      : status === "rejected" || status === "denied"
        ? "bg-coral/15 text-coral"
        : "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300";
  const Icon = status === "ok" ? Check : status === "rejected" || status === "denied" ? ShieldAlert : X;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-black uppercase tracking-wide ${style}`}>
      <Icon className="h-3 w-3" aria-hidden="true" /> {label(status)}
    </span>
  );
}

function Metric({ title, value, icon: Icon, hint }: { title: string; value: string; icon: typeof Clock3; hint?: string }) {
  return (
    <div className="rounded-xl border border-mist bg-white px-3 py-3 dark:border-ink-600 dark:bg-ink-800">
      <div className="flex items-center gap-2 text-neutral-400"><Icon className="h-4 w-4" aria-hidden="true" /><span className="text-[10px] font-black uppercase tracking-wider">{title}</span></div>
      <p className="mt-1 truncate text-sm font-black text-navy-deep dark:text-neutral-100" title={hint}>{value}</p>
    </div>
  );
}

function RunDetail({ run }: { run: AgentRunDetail }) {
  return (
    <section aria-labelledby="run-detail-heading" className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-teal">Selected run</p>
          <h2 id="run-detail-heading" className="mt-1 truncate text-xl font-black text-navy-deep dark:text-neutral-100">{run.agent_name}</h2>
          <p className="mt-1 truncate font-mono text-xs text-neutral-400" title={run.trace_id}>{run.trace_id}</p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric title="Route" value={label(run.route_taken)} icon={Route} />
        <Metric title="Duration" value={duration(run.duration_ms)} icon={Clock3} />
        <Metric title="Tokens" value={run.total_tokens?.toLocaleString() ?? "—"} icon={CircleDashed} />
        {(() => {
          const c = costDisplay(run.total_cost_usd, run.total_tokens);
          return <Metric title="Cost" value={c.text} icon={Coins} hint={c.hint} />;
        })()}
      </div>

      <div className="rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div><p className="text-xs font-black uppercase tracking-[0.14em] text-teal">Executed graph path</p><h3 className="text-sm font-black text-navy-deep dark:text-neutral-100">Ordered node trace</h3></div>
          <span className="text-xs font-bold text-neutral-400">{run.node_steps.length} steps</span>
        </div>
        {run.node_steps.length === 0 ? (
          <p className="rounded-xl bg-ivory p-4 text-sm text-neutral-500 dark:bg-ink-700 dark:text-neutral-300">No node records were captured for this run.</p>
        ) : (
          <ol aria-label="Executed graph path" className="space-y-0">
            {run.node_steps.map((step, index) => (
              <li key={`${step.sequence}-${step.node_name}`} className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-3 pb-4 last:pb-0">
                {index < run.node_steps.length - 1 && <span aria-hidden="true" className="absolute left-[0.94rem] top-8 h-[calc(100%-1rem)] w-px bg-mist dark:bg-ink-600" />}
                <span className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-navy text-xs font-black text-white dark:bg-sky">{step.sequence}</span>
                <div className="min-w-0 rounded-xl bg-ivory px-3 py-3 dark:bg-ink-700">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-black text-navy-deep dark:text-neutral-100">{label(step.node_name)}</p>
                    <div className="flex items-center gap-2">
                      {step.tokens == null && step.cost_usd == null ? (
                        <span
                          title="This node is deterministic — it does not call a language model, so it reports no tokens or cost."
                          className="rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-black uppercase tracking-wide text-neutral-500 dark:bg-ink-600 dark:text-neutral-300"
                        >
                          No LLM call
                        </span>
                      ) : null}
                      <StatusBadge status={step.status} />
                    </div>
                  </div>
                  <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500 dark:text-neutral-300">
                    <div><dt className="inline font-bold">Latency </dt><dd className="inline">{duration(step.duration_ms)}</dd></div>
                    <div><dt className="inline font-bold">Tokens </dt><dd className="inline">{step.tokens?.toLocaleString() ?? "—"}</dd></div>
                    <div><dt className="inline font-bold">Cost </dt>{(() => { const c = costDisplay(step.cost_usd, step.tokens); return <dd className="inline" title={c.hint}>{c.text}</dd>; })()}</div>
                  </dl>
                  {step.notes && <p className="mt-2 break-words text-xs text-neutral-400">{step.notes}</p>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800">
          <div className="mb-3 flex items-center gap-2"><Wrench className="h-4 w-4 text-teal" aria-hidden="true" /><h3 className="text-sm font-black text-navy-deep dark:text-neutral-100">Tools used</h3></div>
          {run.tool_calls.length === 0 ? <p className="text-sm text-neutral-400">No tools were used on this path.</p> : (
            <ul className="space-y-2">{run.tool_calls.map((tool, index) => (
              <li key={`${tool.tool_name}-${index}`} className="min-w-0 rounded-xl bg-ivory p-3 dark:bg-ink-700">
                <div className="flex flex-wrap items-center justify-between gap-2"><p className="break-words text-sm font-black text-navy-deep dark:text-neutral-100">{label(tool.tool_name)}</p><StatusBadge status={tool.status} /></div>
                <p className="mt-1 break-words text-xs text-neutral-500 dark:text-neutral-300">Latency {duration(tool.duration_ms)}{tool.error_type ? ` · Error type: ${label(tool.error_type)}` : ""}</p>
              </li>
            ))}</ul>
          )}
        </div>
        <div className="min-w-0 rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800">
          <h3 className="text-sm font-black text-navy-deep dark:text-neutral-100">Safe final-output preview</h3>
          <p className="mt-1 text-xs text-neutral-400">Only the trace store&rsquo;s redacted, truncated summary is shown.</p>
          <div className="mt-3 min-h-24 break-words rounded-xl bg-ivory p-3 text-sm leading-6 text-neutral-600 dark:bg-ink-700 dark:text-neutral-200">
            {run.output_summary || "Content preview is disabled or unavailable for this run."}
          </div>
        </div>
      </div>
    </section>
  );
}

const RUNS_PER_PAGE = 8;

export function AgentOSDashboard() {
  const [agent, setAgent] = useState("");
  const [status, setStatus] = useState<"" | AgentRunStatus>("");
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [page, setPage] = useState(0);
  // On narrow screens, selecting a run swaps the list out for a focused detail view (with a Back
  // button); on xl the list and detail sit side by side as before.
  const [mobileDetail, setMobileDetail] = useState(false);

  const catalogState = useAutoRefresh(() => getAgentRuns(), [refreshNonce], { intervalMs: 5000 });
  const knownAgents = useMemo(
    () => Array.from(new Set((catalogState.data ?? []).map((run) => run.agent_name))).sort(),
    [catalogState.data],
  );

  const runsState = useAutoRefresh(
    () => getAgentRuns({ agent: agent || undefined, status: status || undefined }),
    [agent, status, refreshNonce],
    { intervalMs: 5000, mapError: (error) => agentError(error).message },
  );
  const runs = useMemo(() => runsState.data ?? [], [runsState.data]);
  const effectiveTrace = selectedTrace && runs.some((run) => run.trace_id === selectedTrace)
    ? selectedTrace
    : runs[0]?.trace_id ?? null;

  const totalPages = Math.max(1, Math.ceil(runs.length / RUNS_PER_PAGE));
  const safePage = Math.min(page, totalPages - 1);
  const pagedRuns = runs.slice(safePage * RUNS_PER_PAGE, safePage * RUNS_PER_PAGE + RUNS_PER_PAGE);

  function selectRun(traceId: string) {
    setSelectedTrace(traceId);
    setMobileDetail(true);
  }

  function changeFilters(next: () => void) {
    next();
    setPage(0);
  }

  const detailState = useAutoRefresh(
    () => effectiveTrace ? getAgentRun(effectiveTrace) : Promise.resolve(null),
    [effectiveTrace, refreshNonce],
    { intervalMs: 5000, mapError: (error) => agentError(error).message },
  );
  const detail = detailState.data?.trace_id === effectiveTrace ? detailState.data : null;
  const selected = useMemo(() => runs.find((run) => run.trace_id === effectiveTrace), [runs, effectiveTrace]);

  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-navy text-white dark:bg-sky"><Bot className="h-6 w-6" aria-hidden="true" /></span><div><p className="text-xs font-black uppercase tracking-[0.14em] text-teal">Agent operations</p><h1 className="text-2xl font-black text-navy-deep dark:text-neutral-100">Agent OS</h1><p className="mt-1 text-sm text-neutral-500 dark:text-neutral-300">Safe execution traces from the self-hosted observability store.</p></div></div>
        <button type="button" onClick={() => setRefreshNonce((value) => value + 1)} className="inline-flex items-center gap-2 rounded-xl border border-mist bg-white px-3 py-2 text-sm font-black text-navy hover:bg-ivory dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100 dark:hover:bg-ink-700"><RefreshCw className="h-4 w-4" aria-hidden="true" />Refresh</button>
      </header>

      <div className="grid gap-5 xl:grid-cols-[390px_minmax(0,1fr)]">
        <aside aria-label="Agent runs" className={`min-w-0 rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800 ${mobileDetail ? "hidden xl:block" : "block"}`}>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <label className="text-xs font-black uppercase tracking-wide text-neutral-500 dark:text-neutral-300">Agent<select aria-label="Filter by agent" value={agent} onChange={(event) => changeFilters(() => setAgent(event.target.value))} className="mt-1 w-full rounded-xl border border-mist bg-white px-3 py-2 text-sm font-bold text-navy-deep dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-100"><option value="">All agents</option>{knownAgents.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
            <label className="text-xs font-black uppercase tracking-wide text-neutral-500 dark:text-neutral-300">Status<select aria-label="Filter by status" value={status} onChange={(event) => changeFilters(() => setStatus(event.target.value as "" | AgentRunStatus))} className="mt-1 w-full rounded-xl border border-mist bg-white px-3 py-2 text-sm font-bold text-navy-deep dark:border-ink-600 dark:bg-ink-700 dark:text-neutral-100">{STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          </div>
          <div className="my-4 flex items-center justify-between"><h2 className="text-sm font-black text-navy-deep dark:text-neutral-100">Recent runs</h2><span className="text-xs font-bold text-neutral-400">{runs.length}</span></div>
          {runsState.loading ? <div role="status" className="space-y-2" aria-label="Loading agent runs">{[1,2,3].map((item) => <div key={item} className="h-24 animate-pulse rounded-xl bg-mist dark:bg-ink-700" />)}</div> : runsState.error ? <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm font-bold text-red-700 dark:bg-red-950/40 dark:text-red-300"><AlertTriangle className="mb-2 h-5 w-5" aria-hidden="true" />{runsState.error}</div> : runs.length === 0 ? <div className="rounded-xl bg-ivory p-5 text-center dark:bg-ink-700"><CircleDashed className="mx-auto h-6 w-6 text-neutral-400" aria-hidden="true" /><p className="mt-2 text-sm font-black text-navy-deep dark:text-neutral-100">No runs found</p><p className="mt-1 text-xs text-neutral-400">Try another filter or wait for the agent to run.</p></div> : (
            <>
              <div role="listbox" aria-label="Recent agent runs" className="space-y-2">{pagedRuns.map((run: AgentRunSummary) => (
                <button key={run.trace_id} type="button" role="option" aria-selected={run.trace_id === effectiveTrace} onClick={() => selectRun(run.trace_id)} className={`w-full min-w-0 rounded-xl border p-3 text-left transition ${run.trace_id === effectiveTrace ? "border-sky bg-mist/70 dark:border-sky dark:bg-ink-700" : "border-mist hover:border-sky/60 hover:bg-ivory dark:border-ink-600 dark:hover:bg-ink-700"}`}>
                  <div className="flex items-center justify-between gap-2"><p className="truncate text-sm font-black text-navy-deep dark:text-neutral-100">{run.agent_name}</p><ChevronRight className="h-4 w-4 shrink-0 text-neutral-400" aria-hidden="true" /></div><div className="mt-2 flex flex-wrap items-center gap-2"><StatusBadge status={run.status} /><span className="text-xs font-bold text-neutral-400">{label(run.route_taken)}</span></div><div className="mt-2 flex items-center justify-between gap-2 text-xs text-neutral-400"><span>{when(run.started_at)}</span><span>{duration(run.duration_ms)} · {run.total_tokens ?? "—"} tok</span></div>{run.guardrail_trigger_count > 0 && <p className="mt-2 flex items-center gap-1 text-xs font-bold text-coral"><ShieldAlert className="h-3 w-3" aria-hidden="true" />{run.guardrail_trigger_count} guardrail trigger{run.guardrail_trigger_count === 1 ? "" : "s"}</p>}
                </button>
              ))}</div>
              {totalPages > 1 ? (
                <div className="mt-4 flex items-center justify-between gap-2">
                  <button type="button" onClick={() => setPage((value) => Math.max(0, value - 1))} disabled={safePage === 0} className="inline-flex items-center gap-1 rounded-lg border border-mist px-3 py-1.5 text-xs font-black text-navy transition hover:bg-ivory disabled:opacity-40 dark:border-ink-600 dark:text-neutral-100 dark:hover:bg-ink-700"><ChevronLeft className="h-4 w-4" aria-hidden="true" />Prev</button>
                  <span className="text-xs font-bold text-neutral-400">Page {safePage + 1} of {totalPages}</span>
                  <button type="button" onClick={() => setPage((value) => Math.min(totalPages - 1, value + 1))} disabled={safePage >= totalPages - 1} className="inline-flex items-center gap-1 rounded-lg border border-mist px-3 py-1.5 text-xs font-black text-navy transition hover:bg-ivory disabled:opacity-40 dark:border-ink-600 dark:text-neutral-100 dark:hover:bg-ink-700">Next<ChevronRight className="h-4 w-4" aria-hidden="true" /></button>
                </div>
              ) : null}
            </>
          )}
        </aside>

        <main className={`min-w-0 rounded-2xl border border-mist bg-neutral-50 p-4 dark:border-ink-600 dark:bg-ink-900 sm:p-5 ${mobileDetail ? "block" : "hidden xl:block"}`}>
          <button type="button" onClick={() => setMobileDetail(false)} className="mb-4 inline-flex items-center gap-1 rounded-lg border border-mist bg-white px-3 py-1.5 text-xs font-black text-navy transition hover:bg-ivory dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100 xl:hidden"><ChevronLeft className="h-4 w-4" aria-hidden="true" />Back to runs</button>
          {!selected ? <div className="flex min-h-72 items-center justify-center text-center"><div><Route className="mx-auto h-8 w-8 text-neutral-300" aria-hidden="true" /><p className="mt-3 text-sm font-black text-neutral-500 dark:text-neutral-300">Select a run to inspect its exact graph path.</p></div></div> : detailState.error ? <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm font-bold text-red-700 dark:bg-red-950/40 dark:text-red-300">{detailState.error}</div> : !detail ? <div role="status" className="flex min-h-72 items-center justify-center"><RefreshCw className="h-6 w-6 animate-spin text-teal" aria-hidden="true" /><span className="sr-only">Loading selected run</span></div> : <RunDetail run={detail} />}
        </main>
      </div>
    </div>
  );
}
