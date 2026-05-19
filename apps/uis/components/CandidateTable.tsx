// Candidate list table. Client component because it reads the URL (search params)
// and fires `fetch` whenever filters change.
//
// Key pattern: the URL is the single source of truth for "what should be shown."
// This component never holds filter state of its own — it reads `searchParams`,
// fetches, and renders. <CandidateFilters /> writes to the URL; the URL change
// re-renders this component; the effect refetches. Browser back/forward and
// page refresh "just work" because the state lives in the URL.

"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getCandidates, errorMessage } from "@/lib/api";
import { isStage, isStatus } from "@/lib/labels";
import type { Candidate } from "@/lib/types";
import { StageBadge } from "@/components/StageBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

function formatDate(value: string) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

// Loading skeleton: 8 placeholder rows with the same column widths as the real
// table. The user sees the layout settle instantly and the spinner only spins
// in the header — much less jarring than a blank table or a single spinner.
function CandidateTableSkeleton() {
  return (
    <tbody className="divide-y divide-neutral-200">
      {Array.from({ length: 8 }).map((_, index) => (
        <tr key={index} className="animate-pulse">
          <td className="px-4 py-3">
            <div className="h-4 w-40 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-3">
            <div className="h-4 w-48 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-3">
            <div className="h-6 w-24 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-3">
            <div className="h-6 w-32 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-3">
            <div className="h-4 w-28 rounded bg-neutral-100" />
          </td>
        </tr>
      ))}
    </tbody>
  );
}

export function CandidateTable() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // Re-read filters from the URL on every render. `useSearchParams` returns a
  // stable object that updates when the URL changes, so when CandidateFilters
  // calls `router.replace`, this component re-renders and the effect below re-fires.
  const rawStatus = searchParams.get("status");
  const rawStage = searchParams.get("stage");
  const status = isStatus(rawStatus) ? rawStatus : undefined;
  const stage = isStage(rawStage) ? rawStage : undefined;
  const q = searchParams.get("q")?.trim() || undefined;

  // Fetch effect, re-runs whenever any filter changes (status/stage/q) or the
  // user clicks "Try again" (reloadKey++). Two important details:
  //
  //   1. `active` flag prevents a stale fetch from overwriting a fresh one.
  //      If the user types quickly, an in-flight request may resolve AFTER a
  //      newer one. We flip `active = false` in cleanup so the stale resolve
  //      can't call `setCandidates`. This is the standard React idiom for
  //      cancellable async work without AbortController.
  //
  //   2. On error we clear the table — leaving stale rows visible would
  //      misrepresent the API state.
  useEffect(() => {
    let active = true;

    async function loadCandidates() {
      setLoading(true);
      setError("");

      try {
        const nextCandidates = await getCandidates({ status, stage, q });
        if (active) {
          setCandidates(nextCandidates);
        }
      } catch (requestError) {
        if (active) {
          setCandidates([]);
          setError(errorMessage(requestError));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadCandidates();

    return () => {
      active = false;
    };
  }, [status, stage, q, reloadKey]);

  function openCandidate(candidate: Candidate) {
    router.push(`/candidates/${candidate.id}`);
  }

  return (
    <section className="rounded-lg border border-neutral-200 bg-white shadow-sm" aria-label="Candidate list">
      <div className="flex min-h-14 items-center justify-between border-b border-neutral-200 px-4 py-3">
        <div>
          <h2 className="text-lg font-semibold text-navy-deep">Candidates</h2>
          <p className="text-sm text-neutral-500">
            {loading ? "Loading records" : `${candidates.length} candidate${candidates.length === 1 ? "" : "s"}`}
          </p>
        </div>
        {loading ? <Spinner label="Updating" /> : null}
      </div>

      {error ? (
        <div className="m-4 rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          <p className="font-semibold">Could not load candidates.</p>
          <p className="mt-1">{error}</p>
          <Button className="mt-3" variant="secondary" onClick={() => setReloadKey((key) => key + 1)}>
            Try again
          </Button>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-mist text-xs uppercase tracking-wide text-neutral-700">
            <tr>
              <th scope="col" className="px-4 py-3 font-semibold">
                Full name
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Position
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Status
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Stage
              </th>
              <th scope="col" className="px-4 py-3 font-semibold">
                Application date
              </th>
            </tr>
          </thead>

          {loading ? (
            <CandidateTableSkeleton />
          ) : (
            <tbody className="divide-y divide-neutral-200">
              {candidates.map((candidate) => (
                // Whole row is clickable. `tabIndex={0}` makes it keyboard-focusable,
                // and the onKeyDown handler activates Enter so the row behaves like a
                // proper link for keyboard users. Together with the focus-visible
                // styling, this satisfies the spec's accessibility requirement.
                <tr
                  key={candidate.id}
                  tabIndex={0}
                  className="cursor-pointer transition-colors hover:bg-ivory focus-visible:bg-ivory"
                  onClick={() => openCandidate(candidate)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      openCandidate(candidate);
                    }
                  }}
                >
                  <td className="whitespace-nowrap px-4 py-3 font-semibold text-navy-deep">
                    {candidate.full_name}
                    <span className="mt-0.5 block text-xs font-normal text-neutral-500">{candidate.email}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-neutral-700">{candidate.position}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <StatusBadge status={candidate.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <StageBadge stage={candidate.stage} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-neutral-700">
                    {formatDate(candidate.application_date)}
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>

      {!loading && !error && candidates.length === 0 ? (
        <div className="border-t border-neutral-200 px-4 py-10 text-center">
          <p className="font-semibold text-navy-deep">No candidates match these filters.</p>
          <p className="mt-1 text-sm text-neutral-500">Try another status, stage, or search term.</p>
        </div>
      ) : null}
    </section>
  );
}
