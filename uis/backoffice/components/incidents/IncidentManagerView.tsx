"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardList, Loader2, Plus, RefreshCw } from "lucide-react";
import { StatCard } from "@/components/StatCard";
import {
  createIncident,
  getIncidentSummary,
  IncidentRequestError,
  listIncidents,
  updateIncidentStatus,
} from "@/lib/incident-api";
import {
  BRANCH_LABELS,
  CATEGORY_LABELS,
  INCIDENT_BRANCHES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_STATUSES,
  ORIGIN_LABELS,
  STATUS_LABELS,
  type Incident,
  type IncidentBranch,
  type IncidentCategory,
  type IncidentCreate,
  type IncidentFilters,
  type IncidentOrigin,
  type IncidentStatus,
  type IncidentSummary,
} from "@/lib/incident-types";

const EMPTY_FORM: IncidentCreate = {
  title: "",
  description: "",
  category: "lost_parcel",
  origin: "branch",
  branch: "la_warehouse",
};

const NEXT_STATUSES: Record<IncidentStatus, IncidentStatus[]> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};

function errorMessage(error: unknown) {
  return error instanceof IncidentRequestError
    ? error.detail.message
    : "The incident service could not complete the request. Please try again.";
}

function SelectField({
  label,
  value,
  onChange,
  children,
  highlighted = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  highlighted?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-xs font-black uppercase tracking-[0.14em] text-neutral-600">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`mt-2 h-12 w-full rounded-lg border px-3 text-sm font-bold text-navy transition ${
          highlighted
            ? "border-coral bg-coral/5 ring-2 ring-coral/15"
            : "border-mist bg-white"
        }`}
      >
        {children}
      </select>
    </label>
  );
}

function Breakdown({
  title,
  values,
  labels,
}: {
  title: string;
  values: Record<string, number>;
  labels: Record<string, string>;
}) {
  return (
    <section className="rounded-lg border border-mist bg-white p-4 shadow-sm">
      <h2 className="text-sm font-black text-navy-deep">{title}</h2>
      <ul className="mt-3 space-y-2">
        {Object.entries(values).map(([key, count]) => (
          <li key={key} className="flex items-center justify-between gap-3 text-sm">
            <span className="font-semibold text-neutral-600">{labels[key] ?? key}</span>
            <span className="rounded-md bg-ivory px-2 py-1 font-black tabular-nums text-navy">{count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function IncidentManagerView() {
  const [form, setForm] = useState<IncidentCreate>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formPending, setFormPending] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [filters, setFilters] = useState<IncidentFilters>({});
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [listPending, setListPending] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutatingId, setMutatingId] = useState<number | null>(null);

  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [summaryPending, setSummaryPending] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setListPending(true);
    setListError(null);
    try {
      const page = await listIncidents(filters);
      setIncidents(page.items);
      setTotal(page.total);
    } catch (error) {
      setListError(errorMessage(error));
    } finally {
      setListPending(false);
    }
  }, [filters]);

  const loadSummary = useCallback(async () => {
    setSummaryPending(true);
    setSummaryError(null);
    try {
      setSummary(await getIncidentSummary());
    } catch (error) {
      setSummaryError(errorMessage(error));
    } finally {
      setSummaryPending(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void listIncidents(filters)
      .then((page) => {
        if (active) {
          setIncidents(page.items);
          setTotal(page.total);
        }
      })
      .catch((error: unknown) => active && setListError(errorMessage(error)))
      .finally(() => active && setListPending(false));
    return () => {
      active = false;
    };
  }, [filters]);

  useEffect(() => {
    let active = true;
    void getIncidentSummary()
      .then((value) => active && setSummary(value))
      .catch((error: unknown) => active && setSummaryError(errorMessage(error)))
      .finally(() => active && setSummaryPending(false));
    return () => {
      active = false;
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!form.title.trim()) errors.title = "Title is required.";
    if (form.description.trim().length < 5) errors.description = "Enter at least five characters.";
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }
    setFormPending(true);
    setFormError(null);
    setFormMessage(null);
    setFieldErrors({});
    try {
      await createIncident({ ...form, title: form.title.trim(), description: form.description.trim() });
      setForm(EMPTY_FORM);
      setFormMessage("Incident registered successfully.");
      await Promise.all([loadList(), loadSummary()]);
    } catch (error) {
      if (error instanceof IncidentRequestError) setFieldErrors(error.detail.fields);
      setFormError(errorMessage(error));
    } finally {
      setFormPending(false);
    }
  }

  async function changeStatus(incident: Incident, status: IncidentStatus) {
    const previous = incident.status;
    setMutationError(null);
    setMutatingId(incident.id);
    setIncidents((items) => items.map((item) => (item.id === incident.id ? { ...item, status } : item)));
    try {
      const updated = await updateIncidentStatus(incident.id, status);
      setIncidents((items) => items.map((item) => (item.id === incident.id ? updated : item)));
      await loadSummary();
    } catch (error) {
      setIncidents((items) =>
        items.map((item) => (item.id === incident.id ? { ...item, status: previous } : item)),
      );
      setMutationError(errorMessage(error));
    } finally {
      setMutatingId(null);
    }
  }

  function changeFilters(next: IncidentFilters) {
    setListPending(true);
    setListError(null);
    setFilters(next);
  }

  return (
    <div className="space-y-8">
      <header className="border-b border-mist pb-6">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Operations</p>
        <h1 className="mt-2 text-2xl font-black text-navy-deep sm:text-3xl">Centralized Incident Manager</h1>
        <p className="mt-3 max-w-3xl text-neutral-600">
          Register operational incidents, track their lifecycle, and monitor every TrackFlow location.
        </p>
      </header>

      <section className="rounded-lg border border-mist bg-white p-5 shadow-sm" aria-labelledby="new-incident">
        <div className="flex items-center gap-2">
          <Plus className="h-5 w-5 text-coral" aria-hidden="true" />
          <h2 id="new-incident" className="text-lg font-black text-navy-deep">Register an incident</h2>
        </div>
        <form onSubmit={submit} className="mt-5 space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="block">
              <span className="text-xs font-black uppercase tracking-[0.14em] text-neutral-600">Title</span>
              <input
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                className="mt-2 h-12 w-full rounded-lg border border-mist px-3 text-sm font-semibold text-navy"
                maxLength={200}
                aria-invalid={Boolean(fieldErrors.title)}
              />
              {fieldErrors.title ? <span className="mt-1 block text-sm font-bold text-coral">{fieldErrors.title}</span> : null}
            </label>
            <SelectField
              label="Category"
              value={form.category}
              onChange={(value) => setForm({ ...form, category: value as IncidentCategory })}
            >
              {INCIDENT_CATEGORIES.map((value) => <option key={value} value={value}>{CATEGORY_LABELS[value]}</option>)}
            </SelectField>
          </div>
          <label className="block">
            <span className="text-xs font-black uppercase tracking-[0.14em] text-neutral-600">Description</span>
            <textarea
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              className="mt-2 min-h-28 w-full rounded-lg border border-mist p-3 text-sm font-semibold text-navy"
              maxLength={5000}
              aria-invalid={Boolean(fieldErrors.description)}
            />
            {fieldErrors.description ? (
              <span className="mt-1 block text-sm font-bold text-coral">{fieldErrors.description}</span>
            ) : null}
          </label>
          <div className="grid gap-4 lg:grid-cols-2">
            <SelectField
              label="Origin"
              value={form.origin}
              onChange={(value) => setForm({ ...form, origin: value as IncidentOrigin })}
            >
              {INCIDENT_ORIGINS.map((value) => <option key={value} value={value}>{ORIGIN_LABELS[value]}</option>)}
            </SelectField>
            <SelectField
              label="Responsible branch"
              value={form.branch}
              highlighted={form.origin === "branch"}
              onChange={(value) => setForm({ ...form, branch: value as IncidentBranch })}
            >
              {INCIDENT_BRANCHES.map((value) => <option key={value} value={value}>{BRANCH_LABELS[value]}</option>)}
            </SelectField>
          </div>
          {formError ? <p className="rounded-lg bg-coral/10 p-3 text-sm font-bold text-navy">{formError}</p> : null}
          {formMessage ? (
            <p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-bold text-emerald-800">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> {formMessage}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={formPending}
            className="inline-flex h-12 items-center gap-2 rounded-lg bg-coral px-5 text-sm font-black text-white disabled:opacity-60"
          >
            {formPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
            {formPending ? "Registering…" : "Register incident"}
          </button>
        </form>
      </section>

      <section aria-labelledby="incident-summary">
        <div className="flex items-center justify-between">
          <h2 id="incident-summary" className="text-lg font-black text-navy-deep">Operational summary</h2>
          {summaryError ? (
            <button type="button" onClick={() => void loadSummary()} className="inline-flex items-center gap-2 text-sm font-black text-navy">
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> Retry
            </button>
          ) : null}
        </div>
        {summaryPending ? <p className="mt-4 text-sm font-bold text-neutral-600">Loading summary…</p> : null}
        {summaryError ? <p className="mt-4 rounded-lg bg-coral/10 p-3 text-sm font-bold text-navy">{summaryError}</p> : null}
        {summary ? (
          <>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <StatCard label="Total" value={summary.total.toString()} detail="All registered incidents." icon={<ClipboardList className="h-5 w-5" />} />
              {INCIDENT_STATUSES.map((value) => (
                <StatCard key={value} label={STATUS_LABELS[value]} value={summary.by_status[value].toString()} detail="Current lifecycle count." icon={<ClipboardList className="h-5 w-5" />} />
              ))}
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              <Breakdown title="By category" values={summary.by_category} labels={CATEGORY_LABELS} />
              <Breakdown title="By origin" values={summary.by_origin} labels={ORIGIN_LABELS} />
              <Breakdown title="By branch" values={summary.by_branch} labels={BRANCH_LABELS} />
            </div>
          </>
        ) : null}
      </section>

      <section aria-labelledby="incident-list">
        <div>
          <h2 id="incident-list" className="text-lg font-black text-navy-deep">Incidents</h2>
          <p className="text-sm font-semibold text-neutral-600">{total} matching incidents</p>
        </div>
        <div className="mt-4 rounded-lg border border-mist bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-black text-navy-deep">Filter existing incidents</h3>
              <p className="mt-1 text-xs font-semibold text-neutral-500">
                These controls narrow the incident list below. They do not create or edit incidents.
              </p>
            </div>
            {Object.values(filters).some(Boolean) ? (
              <button
                type="button"
                onClick={() => changeFilters({})}
                className="text-sm font-black text-navy underline decoration-mist underline-offset-4"
              >
                Clear filters
              </button>
            ) : null}
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <select aria-label="Filter by status" value={filters.status ?? ""} onChange={(event) => changeFilters({ ...filters, status: event.target.value as IncidentStatus || undefined })} className="h-11 rounded-lg border border-mist bg-white px-3 text-sm font-bold">
              <option value="">All statuses</option>
              {INCIDENT_STATUSES.map((value) => <option key={value} value={value}>{STATUS_LABELS[value]}</option>)}
            </select>
            <select aria-label="Filter by origin" value={filters.origin ?? ""} onChange={(event) => changeFilters({ ...filters, origin: event.target.value as IncidentOrigin || undefined })} className="h-11 rounded-lg border border-mist bg-white px-3 text-sm font-bold">
              <option value="">All origins</option>
              {INCIDENT_ORIGINS.map((value) => <option key={value} value={value}>{ORIGIN_LABELS[value]}</option>)}
            </select>
            <select aria-label="Filter by branch" value={filters.branch ?? ""} onChange={(event) => changeFilters({ ...filters, branch: event.target.value as IncidentBranch || undefined })} className="h-11 rounded-lg border border-mist bg-white px-3 text-sm font-bold">
              <option value="">All branches</option>
              {INCIDENT_BRANCHES.map((value) => <option key={value} value={value}>{BRANCH_LABELS[value]}</option>)}
            </select>
            <select aria-label="Filter by category" value={filters.category ?? ""} onChange={(event) => changeFilters({ ...filters, category: event.target.value as IncidentCategory || undefined })} className="h-11 rounded-lg border border-mist bg-white px-3 text-sm font-bold">
              <option value="">All categories</option>
              {INCIDENT_CATEGORIES.map((value) => <option key={value} value={value}>{CATEGORY_LABELS[value]}</option>)}
            </select>
          </div>
        </div>
        {mutationError ? <p className="mt-4 rounded-lg bg-coral/10 p-3 text-sm font-bold text-navy">{mutationError}</p> : null}
        {listPending ? <p className="mt-5 text-sm font-bold text-neutral-600">Loading incidents…</p> : null}
        {listError ? (
          <div className="mt-5 rounded-lg border border-coral/30 bg-coral/10 p-4">
            <p className="flex items-center gap-2 text-sm font-bold text-navy"><AlertTriangle className="h-4 w-4" />{listError}</p>
            <button type="button" onClick={() => void loadList()} className="mt-3 text-sm font-black text-navy underline">Retry incident list</button>
          </div>
        ) : null}
        {!listPending && !listError && incidents.length === 0 ? (
          <p className="mt-5 rounded-lg border border-mist bg-white p-5 text-sm font-bold text-neutral-600">No incidents match these filters.</p>
        ) : null}
        <div className="mt-5 grid gap-4">
          {incidents.map((incident) => (
            <article key={incident.id} className="rounded-lg border border-mist bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-ivory px-2 py-1 text-xs font-black text-navy">#{incident.id}</span>
                    <span className="rounded-md bg-navy/10 px-2 py-1 text-xs font-black text-navy">{STATUS_LABELS[incident.status]}</span>
                    <span className="text-xs font-bold text-neutral-500">{CATEGORY_LABELS[incident.category]}</span>
                  </div>
                  <h3 className="mt-3 break-words text-base font-black text-navy-deep">{incident.title}</h3>
                  <p className="mt-2 break-words text-sm text-neutral-600">{incident.description}</p>
                  <p className="mt-3 text-xs font-bold text-neutral-500">{BRANCH_LABELS[incident.branch]} · {ORIGIN_LABELS[incident.origin]} · {new Date(incident.created_at).toLocaleString()}</p>
                </div>
                {NEXT_STATUSES[incident.status].length ? (
                  <label className="shrink-0">
                    <span className="text-xs font-black uppercase tracking-[0.12em] text-neutral-500">Advance status</span>
                    <select
                      value=""
                      disabled={mutatingId === incident.id}
                      onChange={(event) => void changeStatus(incident, event.target.value as IncidentStatus)}
                      className="mt-2 h-11 w-full rounded-lg border border-mist bg-white px-3 text-sm font-bold text-navy lg:w-44"
                    >
                      <option value="" disabled>{mutatingId === incident.id ? "Updating…" : "Choose status"}</option>
                      {NEXT_STATUSES[incident.status].map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
                    </select>
                  </label>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
