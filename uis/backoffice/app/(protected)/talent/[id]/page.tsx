import type { Metadata } from "next";
import Link from "next/link";
import { CandidateDetailView } from "@/components/talent/CandidateDetailView";
import { NotFound } from "@/components/talent/NotFound";
import { getCandidate, getNotes, errorMessage, isNotFoundError } from "@/lib/talent/api";
import type { Candidate, Note } from "@/lib/talent/types";
import { buttonClassName } from "@/components/talent/ui/Button";
import { getServerAPIContext } from "@/lib/server/request-context";

export const metadata: Metadata = {
  title: "Candidate Detail - TrackFlow Backoffice",
  description: "Candidate detail, editing, and notes in the talent pipeline.",
};

type CandidatePageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function CandidatePage({ params }: CandidatePageProps) {
  const { id } = await params;
  const apiContext = await getServerAPIContext();

  let data: { candidate: Candidate; notes: Note[] } | undefined;
  let requestError: unknown;
  try {
    const [candidate, notes] = await Promise.all([
      getCandidate(id, apiContext),
      getNotes(id, apiContext),
    ]);
    data = { candidate, notes };
  } catch (caught) {
    requestError = caught;
  }

  if (data) {
    return <CandidateDetailView initialCandidate={data.candidate} initialNotes={data.notes} />;
  }

  if (isNotFoundError(requestError)) {
    return <NotFound />;
  }

  return (
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
  );
}
