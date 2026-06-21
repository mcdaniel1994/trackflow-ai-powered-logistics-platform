import type { Metadata } from "next";
import Link from "next/link";
import { CandidateForm } from "@/components/talent/CandidateForm";

export const metadata: Metadata = {
  title: "Register Candidate - TrackFlow Backoffice",
  description: "Register a new candidate in the talent pipeline.",
};

export default function NewCandidatePage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <Link href="/talent" className="text-sm font-semibold text-navy underline-offset-2 hover:text-coral">
          Back to list
        </Link>
        <p className="mt-4 text-sm font-semibold uppercase tracking-wide text-coral">Talent Pipeline Tracker</p>
        <h1 className="text-2xl font-bold text-navy-deep">Register candidate</h1>
        <p className="mt-2 text-sm text-neutral-700">
          Add candidates who arrive through referrals, direct outreach, or late submissions.
        </p>
      </header>

      <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <CandidateForm mode="create" />
      </section>
    </div>
  );
}
