"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  FileText,
  RefreshCw,
  Upload,
  XCircle,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { decideDepartment, getRfpTicket, getRfpTickets, rfpError, uploadRfp } from "@/lib/rfp/api";
import type { RfpDecisionAction, RfpTicketDetail, RfpTicketSummary } from "@/lib/rfp/types";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";

const DECISIONS: { action: RfpDecisionAction; label: string }[] = [
  { action: "approve", label: "Approve" },
  { action: "request_changes", label: "Request changes" },
  { action: "reject", label: "Reject" },
];

function label(value: string | null) {
  return (value || "—").replaceAll("_", " ");
}

function when(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusStyle(status: string) {
  if (status === "done") return "bg-teal/15 text-teal-700 dark:text-teal";
  if (status === "discarded") return "bg-coral/15 text-coral";
  if (status === "waiting_for_approval") return "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300";
  return "bg-sky/15 text-navy dark:text-sky";
}

function StatusBadge({ status }: { status: string }) {
  const Icon = status === "done" ? CheckCircle2 : status === "discarded" ? XCircle : CircleDashed;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-black uppercase tracking-wide ${statusStyle(status)}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" /> {label(status)}
    </span>
  );
}

function aspectsOf(section: RfpTicketDetail["sections"][number]): string[] {
  const raw = section.key_aspects?.["aspects"];
  return Array.isArray(raw) ? raw.map((item) => String(item)) : [];
}

function TicketDetail({
  ticket,
  onDecide,
  deciding,
}: {
  ticket: RfpTicketDetail;
  onDecide: (department: string, action: RfpDecisionAction) => void;
  deciding: string | null;
}) {
  const awaitingApproval = ticket.status === "waiting_for_approval";
  return (
    <section aria-labelledby="rfp-detail-heading" className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-teal">Selected RFP</p>
          <h2 id="rfp-detail-heading" className="mt-1 truncate text-xl font-black text-navy-deep dark:text-neutral-100">
            {ticket.client_name || ticket.rfp_id}
          </h2>
          <p className="mt-1 truncate font-mono text-xs text-neutral-400">{ticket.rfp_id}</p>
        </div>
        <StatusBadge status={ticket.status} />
      </div>

      {ticket.status === "discarded" && ticket.discard_reason && (
        <p role="note" className="rounded-xl bg-coral/10 p-3 text-sm font-bold text-coral">
          Discarded: {ticket.discard_reason}
        </p>
      )}

      {ticket.status === "done" && (
        <p role="note" className="rounded-xl bg-teal/10 p-3 text-sm font-bold text-teal-700 dark:text-teal">
          Proposal complete — every department approved. The final document is ready.
        </p>
      )}

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric title="Country" value={label(ticket.client_country)} />
        <Metric title="Currency" value={label(ticket.currency)} />
        <Metric title="Volume/mo" value={ticket.monthly_volume?.toLocaleString() ?? "—"} />
        <Metric title="Deadline" value={ticket.deadline_days ? `${ticket.deadline_days} days` : "—"} />
      </dl>

      <div className="rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-black text-navy-deep dark:text-neutral-100">Departments to involve</h3>
          <span className="text-xs font-bold text-neutral-400">{ticket.sections.length}</span>
        </div>
        {ticket.sections.length === 0 ? (
          <p className="rounded-xl bg-ivory p-4 text-sm text-neutral-500 dark:bg-ink-700 dark:text-neutral-300">
            No departments have been routed for this ticket yet.
          </p>
        ) : (
          <ul className="space-y-2">
            {ticket.sections.map((section) => (
              <li key={section.department_id} className="min-w-0 rounded-xl bg-ivory p-3 dark:bg-ink-700">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-black capitalize text-navy-deep dark:text-neutral-100">
                    {label(section.department_id)}
                  </p>
                  <StatusBadge status={section.approval_status} />
                </div>
                {aspectsOf(section).length > 0 && (
                  <ul className="mt-2 list-disc pl-5 text-xs text-neutral-500 dark:text-neutral-300">
                    {aspectsOf(section).map((aspect, index) => (
                      <li key={index}>{aspect}</li>
                    ))}
                  </ul>
                )}
                {section.draft_content && (
                  <p className="mt-2 whitespace-pre-wrap rounded-lg bg-white p-2 text-xs text-neutral-600 dark:bg-ink-800 dark:text-neutral-200">
                    {section.draft_content}
                  </p>
                )}
                {awaitingApproval && section.approval_status === "pending" && (
                  <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={`Approve ${section.department_id}`}>
                    {DECISIONS.map(({ action, label: text }) => (
                      <button
                        key={action}
                        type="button"
                        disabled={deciding === section.department_id}
                        onClick={() => onDecide(section.department_id, action)}
                        className={`rounded-lg px-3 py-1.5 text-xs font-black transition disabled:opacity-50 ${
                          action === "approve"
                            ? "bg-teal text-white hover:bg-teal-700"
                            : action === "reject"
                              ? "bg-coral/15 text-coral hover:bg-coral/25"
                              : "border border-mist text-navy hover:bg-white dark:border-ink-600 dark:text-neutral-100"
                        }`}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border border-mist bg-white px-3 py-3 dark:border-ink-600 dark:bg-ink-800">
      <dt className="text-[10px] font-black uppercase tracking-wider text-neutral-400">{title}</dt>
      <dd className="mt-1 truncate text-sm font-black capitalize text-navy-deep dark:text-neutral-100">{value}</dd>
    </div>
  );
}

export function RfpDesk() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [deciding, setDeciding] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const listState = useAutoRefresh(
    () => getRfpTickets(),
    [refreshNonce],
    { intervalMs: 5000, mapError: (error) => rfpError(error).message },
  );
  const tickets = useMemo(() => listState.data ?? [], [listState.data]);
  const effectiveId =
    selectedId && tickets.some((ticket) => ticket.id === selectedId) ? selectedId : tickets[0]?.id ?? null;

  const detailState = useAutoRefresh(
    () => (effectiveId ? getRfpTicket(effectiveId) : Promise.resolve(null)),
    [effectiveId, refreshNonce],
    { intervalMs: 5000, mapError: (error) => rfpError(error).message },
  );
  const detail = detailState.data?.id === effectiveId ? detailState.data : null;

  async function onDecide(department: string, action: RfpDecisionAction) {
    if (!effectiveId) return;
    setDeciding(department);
    setDecisionError(null);
    try {
      await decideDepartment(effectiveId, department, action);
      setRefreshNonce((value) => value + 1);
    } catch (error) {
      setDecisionError(rfpError(error).message);
    } finally {
      setDeciding(null);
    }
  }

  async function onUpload(file: File) {
    setUploading(true);
    setUploadError(null);
    setUploadNotice(null);
    try {
      const created = await uploadRfp(file);
      setUploadNotice(`Uploaded ${created.rfp_id}. Analyzing…`);
      setSelectedId(created.id);
      setRefreshNonce((value) => value + 1);
    } catch (error) {
      setUploadError(rfpError(error).message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-navy text-white dark:bg-sky">
            <FileText className="h-6 w-6" aria-hidden="true" />
          </span>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.14em] text-teal">Commercial operations</p>
            <h1 className="text-2xl font-black text-navy-deep dark:text-neutral-100">RFP Desk</h1>
            <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-300">
              Upload an RFP PDF and watch it get classified and routed to the right departments.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setRefreshNonce((value) => value + 1)}
          className="inline-flex items-center gap-2 rounded-xl border border-mist bg-white px-3 py-2 text-sm font-black text-navy hover:bg-ivory dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100 dark:hover:bg-ink-700"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </header>

      <div className="rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800">
        <label htmlFor="rfp-file" className="text-sm font-black text-navy-deep dark:text-neutral-100">
          Upload RFP (PDF)
        </label>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <input
            id="rfp-file"
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            aria-label="Upload RFP PDF"
            disabled={uploading}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void onUpload(file);
            }}
            className="block w-full max-w-md text-sm text-neutral-600 file:mr-3 file:rounded-lg file:border-0 file:bg-navy file:px-3 file:py-2 file:text-sm file:font-black file:text-white hover:file:bg-navy-deep dark:text-neutral-300"
          />
          {uploading && (
            <span role="status" className="inline-flex items-center gap-2 text-sm font-bold text-teal">
              <Upload className="h-4 w-4 animate-pulse" aria-hidden="true" /> Uploading…
            </span>
          )}
        </div>
        {uploadNotice && <p className="mt-2 text-sm font-bold text-teal">{uploadNotice}</p>}
        {uploadError && (
          <p role="alert" className="mt-2 flex items-center gap-1 text-sm font-bold text-coral">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" /> {uploadError}
          </p>
        )}
      </div>

      <div className="grid gap-5 xl:grid-cols-[390px_minmax(0,1fr)]">
        <aside
          aria-label="RFP tickets"
          className="min-w-0 rounded-2xl border border-mist bg-white p-4 dark:border-ink-600 dark:bg-ink-800"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-black text-navy-deep dark:text-neutral-100">Tickets</h2>
            <span className="text-xs font-bold text-neutral-400">{tickets.length}</span>
          </div>
          {listState.loading ? (
            <div role="status" aria-label="Loading RFP tickets" className="space-y-2">
              {[1, 2, 3].map((item) => (
                <div key={item} className="h-20 animate-pulse rounded-xl bg-mist dark:bg-ink-700" />
              ))}
            </div>
          ) : listState.error ? (
            <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm font-bold text-red-700 dark:bg-red-950/40 dark:text-red-300">
              {listState.error}
            </div>
          ) : tickets.length === 0 ? (
            <div className="rounded-xl bg-ivory p-5 text-center dark:bg-ink-700">
              <FileText className="mx-auto h-6 w-6 text-neutral-400" aria-hidden="true" />
              <p className="mt-2 text-sm font-black text-navy-deep dark:text-neutral-100">No RFPs yet</p>
              <p className="mt-1 text-xs text-neutral-400">Upload a PDF above to create the first ticket.</p>
            </div>
          ) : (
            <div role="listbox" aria-label="RFP tickets" className="max-h-[64vh] space-y-2 overflow-y-auto pr-1">
              {tickets.map((ticket: RfpTicketSummary) => (
                <button
                  key={ticket.id}
                  type="button"
                  role="option"
                  aria-selected={ticket.id === effectiveId}
                  onClick={() => setSelectedId(ticket.id)}
                  className={`w-full min-w-0 rounded-xl border p-3 text-left transition ${
                    ticket.id === effectiveId
                      ? "border-sky bg-mist/70 dark:border-sky dark:bg-ink-700"
                      : "border-mist hover:border-sky/60 hover:bg-ivory dark:border-ink-600 dark:hover:bg-ink-700"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-black text-navy-deep dark:text-neutral-100">
                      {ticket.client_name || ticket.rfp_id}
                    </p>
                    <ChevronRight className="h-4 w-4 shrink-0 text-neutral-400" aria-hidden="true" />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <StatusBadge status={ticket.status} />
                    {ticket.client_country && (
                      <span className="text-xs font-bold text-neutral-400">{ticket.client_country}</span>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-neutral-400">{when(ticket.updated_at)}</p>
                </button>
              ))}
            </div>
          )}
        </aside>

        <main className="min-w-0 rounded-2xl border border-mist bg-neutral-50 p-4 dark:border-ink-600 dark:bg-ink-900 sm:p-5">
          {!effectiveId ? (
            <div className="flex min-h-72 items-center justify-center text-center">
              <div>
                <FileText className="mx-auto h-8 w-8 text-neutral-300" aria-hidden="true" />
                <p className="mt-3 text-sm font-black text-neutral-500 dark:text-neutral-300">
                  Upload or select an RFP to see its routing.
                </p>
              </div>
            </div>
          ) : detailState.error ? (
            <div role="alert" className="rounded-xl bg-red-50 p-4 text-sm font-bold text-red-700 dark:bg-red-950/40 dark:text-red-300">
              {detailState.error}
            </div>
          ) : !detail ? (
            <div role="status" className="flex min-h-72 items-center justify-center">
              <RefreshCw className="h-6 w-6 animate-spin text-teal" aria-hidden="true" />
              <span className="sr-only">Loading selected RFP</span>
            </div>
          ) : (
            <div className="space-y-3">
              {decisionError && (
                <div role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/40 dark:text-red-300">
                  {decisionError}
                </div>
              )}
              <TicketDetail ticket={detail} onDecide={onDecide} deciding={deciding} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
