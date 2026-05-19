// `/` — the candidate list. This is a Server Component (no "use client" at top):
// it reads URL search params on the server, sanitizes them, then passes safe
// initial values to the client components that handle interactivity below.
//
// The actual fetching happens inside <CandidateTable />, which is a client
// component. We keep this page server-side so the initial HTML always includes
// the page chrome, even if JS is slow to load.

import Link from "next/link";
import { CandidateFilters } from "@/components/CandidateFilters";
import { CandidateTable } from "@/components/CandidateTable";
import { buttonClassName } from "@/components/ui/Button";
import { isStage, isStatus } from "@/lib/labels";

// In Next 15, `searchParams` is a Promise — you must `await` it before reading.
type HomeProps = {
  searchParams?: Promise<{
    status?: string;
    stage?: string;
    q?: string;
  }>;
};

export default async function Home({ searchParams }: HomeProps) {
  const params = (await searchParams) ?? {};
  // The URL is user-controllable; validate before treating it as a typed Status/Stage.
  // Anything bogus falls through to `undefined`, which means "no filter".
  const initialStatus = isStatus(params.status) ? params.status : undefined;
  const initialStage = isStage(params.stage) ? params.stage : undefined;
  const initialQ = params.q?.trim() || undefined;

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-coral">Talent Pipeline Tracker</p>
          <h1 className="text-2xl font-bold text-navy-deep">Executive Assistant — Zaragoza HQ</h1>
        </div>
        <Link href="/candidates/new" className={buttonClassName("primary")}>
          Register candidate
        </Link>
      </header>

      <CandidateFilters initialStatus={initialStatus} initialStage={initialStage} initialQ={initialQ} />
      <CandidateTable />
    </main>
  );
}
