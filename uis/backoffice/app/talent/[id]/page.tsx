// `/talent/[id]` — dynamic route. The `[id]` folder name turns into a URL
// parameter that arrives in `params.id`. This page is a Server Component that
// fetches the candidate + notes on the server, then hands them to a client
// component for interactive bits (edit form, inline status select, notes panel).
//
// Server-side fetching here gives us two wins:
//   1. The detail page renders fully-formed HTML on first paint (no spinner flash).
//   2. We can branch on the API response — 404 -> friendly NotFound, network
//      failure -> recoverable error card. The client never sees a half-broken state.

import type { Metadata } from "next";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CandidateDetailView } from "@/components/talent/CandidateDetailView";
import { NotFound } from "@/components/talent/NotFound";
import { getCandidate, getNotes, errorMessage, isNotFoundError } from "@/lib/talent/api";
import type { Candidate, Note } from "@/lib/talent/types";
import { buttonClassName } from "@/components/talent/ui/Button";

export const metadata: Metadata = {
  title: "Candidate Detail — TrackFlow Backoffice",
  description: "Candidate detail, editing, and notes in the talent pipeline.",
};

type CandidatePageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function CandidatePage({ params }: CandidatePageProps) {
  const { id } = await params;

  // The try block only fetches — JSX is constructed after it, so rendering
  // errors are never swallowed by this catch (they belong to error boundaries).
  let data: { candidate: Candidate; notes: Note[] } | undefined;
  let requestError: unknown;
  try {
    // `Promise.all` runs both fetches in parallel — total latency is max(candidate, notes)
    // rather than candidate + notes. If either fails, we drop into the catch below.
    const [candidate, notes] = await Promise.all([getCandidate(id), getNotes(id)]);
    data = { candidate, notes };
  } catch (caught) {
    requestError = caught;
  }

  if (data) {
    return (
      <AppShell>
        <CandidateDetailView initialCandidate={data.candidate} initialNotes={data.notes} />
      </AppShell>
    );
  }

  // 404 (or 422 from this particular mock API) -> show the friendly not-found view.
  // Any other error (network, 500, etc.) falls through to the recoverable error card.
  if (isNotFoundError(requestError)) {
    return (
      <AppShell>
        <NotFound />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl py-10">
        <div className="rounded-lg border border-coral/30 bg-white p-8 text-center shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-wide text-coral">Could not load candidate</p>
          <h1 className="mt-2 text-2xl font-bold text-navy-deep">The tracker could not reach this record.</h1>
          <p className="mt-3 text-sm text-neutral-700">{errorMessage(requestError)}</p>
          <Link href="/talent" className={buttonClassName("primary", "mt-6")}>
            Back to list
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
