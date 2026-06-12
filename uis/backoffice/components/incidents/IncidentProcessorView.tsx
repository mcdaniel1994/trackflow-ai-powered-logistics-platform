"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Globe2,
  ListChecks,
  Loader2,
  ShieldAlert,
  SmilePlus,
  Upload,
} from "lucide-react";
import { StatCard } from "@/components/StatCard";
import { analyzeIncidentCsv, getIncidentExportUrl } from "@/lib/incident-api";
import type {
  IncidentAnalysisResult,
  IncidentInvalidRule,
  IncidentMetricBreakdown,
  IncidentSatisfactionScore,
} from "@/lib/incident-types";

function formatPercent(value: string) {
  return `${value}%`;
}

function nonzeroRules(rules: IncidentInvalidRule[]) {
  return rules.filter((rule) => rule.count > 0);
}

function BreakdownList({
  title,
  icon,
  items,
}: {
  title: string;
  icon: React.ReactNode;
  items: IncidentMetricBreakdown[];
}) {
  return (
    <section className="rounded-lg border border-mist bg-white p-5 shadow-sm" aria-labelledby={`${title}-heading`}>
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-mist bg-ivory text-navy">
          {icon}
        </div>
        <h2 id={`${title}-heading`} className="text-base font-black text-navy-deep">
          {title}
        </h2>
      </div>
      <ul className="mt-4 space-y-3">
        {items.map((item) => (
          <li key={item.code} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-sm">
            <span className="min-w-0 break-words font-bold text-navy">{item.code}</span>
            <span className="whitespace-nowrap rounded-md bg-ivory px-2 py-1 font-black tabular-nums text-navy">
              {item.count} / {formatPercent(item.percentage)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SatisfactionList({ scores }: { scores: IncidentSatisfactionScore[] }) {
  return (
    <section className="rounded-lg border border-mist bg-white p-5 shadow-sm" aria-labelledby="satisfaction-heading">
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-mist bg-ivory text-navy">
          <SmilePlus className="h-5 w-5" aria-hidden="true" />
        </div>
        <h2 id="satisfaction-heading" className="text-base font-black text-navy-deep">
          Satisfaction Distribution
        </h2>
      </div>
      <ul className="mt-4 space-y-3">
        {scores.map((item) => (
          <li key={item.score} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-sm">
            <span className="min-w-0 break-words font-bold text-navy">
              Score {item.score} ({item.label})
            </span>
            <span className="whitespace-nowrap rounded-md bg-ivory px-2 py-1 font-black tabular-nums text-navy">
              {item.count}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function InvalidRules({ rules }: { rules: IncidentInvalidRule[] }) {
  const activeRules = nonzeroRules(rules);

  return (
    <section className="rounded-lg border border-mist bg-white p-5 shadow-sm" aria-labelledby="invalid-rules-heading">
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-mist bg-ivory text-navy">
          <ShieldAlert className="h-5 w-5" aria-hidden="true" />
        </div>
        <h2 id="invalid-rules-heading" className="text-base font-black text-navy-deep">
          Invalid Records Breakdown
        </h2>
      </div>
      {activeRules.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {activeRules.map((rule) => (
            <li key={rule.code} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-sm">
              <span className="min-w-0 break-words font-bold text-navy">{rule.label}</span>
              <span className="whitespace-nowrap rounded-md bg-coral/10 px-2 py-1 font-black tabular-nums text-navy ring-1 ring-coral/25">
                {rule.count}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm font-semibold text-neutral-600">No invalid records.</p>
      )}
    </section>
  );
}

export function IncidentProcessorView() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<IncidentAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const exportUrl = useMemo(() => (result ? getIncidentExportUrl() : ""), [result]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a CSV file before running analysis.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      setResult(await analyzeIncidentCsv(file));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Incident processor request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-col justify-between gap-4 border-b border-mist pb-6 lg:flex-row lg:items-end">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">
            Customer Experience
          </p>
          <h1 className="mt-2 max-w-3xl break-words text-2xl font-black leading-tight text-navy-deep sm:text-3xl">
            Incident Report Processor
          </h1>
          <p className="mt-3 max-w-[20rem] break-words text-neutral-600 sm:max-w-3xl">
            Aggregate incident volume, quality, and satisfaction signals from the latest CSV export.
          </p>
        </div>
        {result ? (
          <a
            href={exportUrl}
            className="inline-flex w-fit items-center gap-2 rounded-lg border border-navy bg-navy px-3 py-2 text-sm font-black text-white shadow-sm transition hover:bg-navy-deep"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Export CSV
          </a>
        ) : null}
      </header>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-lg border border-mist bg-white p-4 shadow-sm md:flex-row md:items-end"
      >
        <label className="min-w-0 flex-1">
          <span className="text-xs font-black uppercase tracking-[0.16em] text-neutral-500">
            Incident CSV
          </span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-2 block w-full min-w-0 rounded-lg border border-mist bg-neutral-50 px-3 py-2 text-sm font-semibold text-navy file:mr-3 file:rounded-md file:border-0 file:bg-navy file:px-3 file:py-1.5 file:text-sm file:font-black file:text-white"
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-coral bg-coral px-4 text-sm font-black text-white shadow-sm transition hover:bg-coral/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Upload className="h-4 w-4" aria-hidden="true" />
          )}
          Analyze
        </button>
      </form>

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-coral/35 bg-coral/10 p-4 text-sm font-bold text-navy">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-coral" aria-hidden="true" />
          <p className="min-w-0 break-words">{error}</p>
        </div>
      ) : null}

      {result ? (
        <>
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Incident summary">
            <StatCard
              label="Total Rows"
              value={result.total_records.toString()}
              detail="Rows parsed from the uploaded CSV export."
              icon={<FileSpreadsheet className="h-5 w-5" aria-hidden="true" />}
            />
            <StatCard
              label="Valid Records"
              value={result.valid_records.toString()}
              detail="Rows included in aggregate CX metrics."
              icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
            />
            <StatCard
              label="Invalid Records"
              value={result.invalid_records.toString()}
              detail="Rows excluded after validation."
              icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
            />
            <StatCard
              label="Avg Satisfaction"
              value={`${result.satisfaction.average_score} / 5.00`}
              detail={`${result.satisfaction.scored_incidents} scored closed incidents.`}
              icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
            />
          </section>

          <section className="grid gap-4 xl:grid-cols-2" aria-label="Incident validation and satisfaction">
            <InvalidRules rules={result.invalid_rules} />
            <SatisfactionList scores={result.satisfaction.scores} />
          </section>

          <section className="grid gap-4 xl:grid-cols-3" aria-label="Incident breakdowns">
            <BreakdownList
              title="Category"
              icon={<ListChecks className="h-5 w-5" aria-hidden="true" />}
              items={result.categories}
            />
            <BreakdownList
              title="Status"
              icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
              items={result.statuses}
            />
            <BreakdownList
              title="Country"
              icon={<Globe2 className="h-5 w-5" aria-hidden="true" />}
              items={result.countries}
            />
          </section>

          {result.validation_errors.length > 0 ? (
            <section className="rounded-lg border border-mist bg-white p-5 shadow-sm" aria-labelledby="safe-errors-heading">
              <h2 id="safe-errors-heading" className="text-base font-black text-navy-deep">
                Validation Errors
              </h2>
              <ul className="mt-4 grid gap-2 md:grid-cols-2">
                {result.validation_errors.slice(0, 12).map((item, index) => (
                  <li
                    key={`${item.row_number}-${item.field}-${item.code}-${index}`}
                    className="rounded-md border border-mist bg-neutral-50 px-3 py-2 text-sm font-bold text-navy"
                  >
                    Row {item.row_number} / {item.field} / {item.code}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

