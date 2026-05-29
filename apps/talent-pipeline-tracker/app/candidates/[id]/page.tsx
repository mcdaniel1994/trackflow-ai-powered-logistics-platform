// `/candidates/[id]` — dynamic route. The `[id]` folder name turns into a URL
// parameter that arrives in `params.id`. This page is a Server Component that
// fetches the candidate + notes on the server, then hands them to a client
// component for interactive bits (edit form, inline status select, notes panel).
//
// Server-side fetching here gives us two wins:
//   1. The detail page renders fully-formed HTML on first paint (no spinner flash).
//   2. We can branch on the API response — 404 -> friendly NotFound, network
//      failure -> recoverable error card. The client never sees a half-broken state.

import Link from "next/link";
import { CandidateDetailView } from "@/components/CandidateDetailView";
import { NotFound } from "@/components/NotFound";
import { getCandidate, getNotes, errorMessage, isNotFoundError } from "@/lib/api";
import { buttonClassName } from "@/components/ui/Button";

type CandidatePageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function CandidatePage({ params }: CandidatePageProps) {
  const { id } = await params;

  try {
    // `Promise.all` runs both fetches in parallel — total latency is max(candidate, notes)
    // rather than candidate + notes. If either fails, we drop into the catch below.
    const [candidate, notes] = await Promise.all([getCandidate(id), getNotes(id)]);
    return <CandidateDetailView initialCandidate={candidate} initialNotes={notes} />;
  } catch (requestError) {
    // 404 (or 422 from this particular mock API) -> show the friendly not-found view.
    // Any other error (network, 500, etc.) falls through to the recoverable error card.
    if (isNotFoundError(requestError)) {
      return <NotFound />;
    }

    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <div className="rounded-lg border border-coral/30 bg-white p-8 text-center shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-wide text-coral">Could not load candidate</p>
          <h1 className="mt-2 text-2xl font-bold text-navy-deep">The tracker could not reach this record.</h1>
          <p className="mt-3 text-sm text-neutral-700">{errorMessage(requestError)}</p>
          <Link href="/" className={buttonClassName("primary", "mt-6")}>
            Back to list
          </Link>
        </div>
      </main>
    );
  }
}
