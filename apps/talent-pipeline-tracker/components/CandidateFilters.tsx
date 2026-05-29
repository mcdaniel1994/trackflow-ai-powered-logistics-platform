// Filter row above the candidate table. Writes URL search params; never holds
// "applied filter" state of its own. CandidateTable then reads the URL and
// refetches. This is the pair to the URL-driven pattern documented in
// CandidateTable.tsx — keep both halves in mind when changing either.
//
// Search input is the one local-state exception (typing is per-keystroke), but
// it's still debounced into the URL after 300ms so the URL stays the truth.

"use client";

import { useEffect, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { isStage, isStatus, stageLabel, stageOptions, statusLabel, statusOptions } from "@/lib/labels";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

type CandidateFiltersProps = {
  initialStatus?: string;
  initialStage?: string;
  initialQ?: string;
};

export function CandidateFilters({ initialStatus, initialStage, initialQ }: CandidateFiltersProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const rawStatus = searchParams.get("status");
  const rawStage = searchParams.get("stage");
  const currentStatus = isStatus(rawStatus) ? rawStatus : initialStatus ?? "";
  const currentStage = isStage(rawStage) ? rawStage : initialStage ?? "";
  const currentQ = searchParams.get("q") ?? initialQ ?? "";
  const [searchValue, setSearchValue] = useState(currentQ);

  // Single helper for "update one URL param." Empty string -> remove the param
  // entirely (so the URL stays clean: `/?status=selected` rather than `/?status=`).
  //
  // `router.replace` updates the URL without pushing a new history entry — picking
  // a filter shouldn't pollute the back button.
  //
  // `startTransition` marks the navigation as low-priority, so React keeps the
  // UI interactive while the table refetches. `isPending` flips true during the
  // transition, which we use to disable selects momentarily.
  function replaceParam(name: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());

    if (value) {
      params.set(name, value);
    } else {
      params.delete(name);
    }

    const query = params.toString();
    startTransition(() => {
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    });
  }

  // Keep the search input in sync if the URL changes from outside this component
  // (e.g. back/forward navigation, the "Clear" button below).
  useEffect(() => {
    setSearchValue(currentQ);
  }, [currentQ]);

  // Debounced search: wait 300ms after the user stops typing before pushing the
  // value into the URL. Prevents a fetch on every keystroke. Each keystroke
  // restarts the timer via the cleanup function.
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const nextValue = searchValue.trim();
      if (nextValue !== currentQ) {
        replaceParam("q", nextValue);
      }
    }, 300);

    return () => window.clearTimeout(timeout);
  }, [currentQ, searchValue]);

  const hasFilters = Boolean(currentStatus || currentStage || currentQ);

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm" aria-label="Candidate filters">
      <div className="grid gap-4 md:grid-cols-[1fr_220px_240px_auto] md:items-end">
        <div className="space-y-1.5">
          <label htmlFor="candidate-search" className="block text-sm font-semibold text-navy-deep">
            Search
          </label>
          <Input
            id="candidate-search"
            type="search"
            value={searchValue}
            onChange={(event) => setSearchValue(event.target.value)}
            placeholder="Name or email"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="status-filter" className="block text-sm font-semibold text-navy-deep">
            Status
          </label>
          <Select
            id="status-filter"
            value={currentStatus}
            onChange={(event) => replaceParam("status", event.target.value)}
            disabled={isPending}
          >
            <option value="">All statuses</option>
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="stage-filter" className="block text-sm font-semibold text-navy-deep">
            Stage
          </label>
          <Select
            id="stage-filter"
            value={currentStage}
            onChange={(event) => replaceParam("stage", event.target.value)}
            disabled={isPending}
          >
            <option value="">All stages</option>
            {stageOptions.map((stage) => (
              <option key={stage} value={stage}>
                {stageLabel(stage)}
              </option>
            ))}
          </Select>
        </div>

        <Button
          variant="secondary"
          onClick={() => {
            setSearchValue("");
            startTransition(() => {
              router.replace(pathname, { scroll: false });
            });
          }}
          disabled={!hasFilters || isPending}
        >
          Clear
        </Button>
      </div>
    </section>
  );
}
