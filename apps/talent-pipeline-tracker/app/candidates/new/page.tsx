// `/candidates/new` — dedicated registration route (per spec decision: not a modal).
// All this page does is render <CandidateForm mode="create" />. The shared form
// component handles validation, submission, and the redirect to the new detail page.

import Link from "next/link";
import { CandidateForm } from "@/components/CandidateForm";

export default function NewCandidatePage() {
  return (
    <main className="mx-auto max-w-4xl space-y-6 px-6 py-6">
      <header>
        <Link href="/" className="text-sm font-semibold text-navy underline-offset-2 hover:text-coral">
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
    </main>
  );
}
