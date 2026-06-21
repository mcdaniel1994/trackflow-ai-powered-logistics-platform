import type { Metadata } from "next";
import Link from "next/link";
import { CandidateFilters } from "@/components/talent/CandidateFilters";
import { CandidateTable } from "@/components/talent/CandidateTable";
import { buttonClassName } from "@/components/talent/ui/Button";
import { isStage, isStatus } from "@/lib/talent/labels";

export const metadata: Metadata = {
  title: "Talent Pipeline - TrackFlow Backoffice",
  description: "Internal candidate management for the Executive Assistant search at Zaragoza HQ.",
};

type TalentPageProps = {
  searchParams?: Promise<{
    status?: string;
    stage?: string;
    q?: string;
  }>;
};

export default async function TalentPage({ searchParams }: TalentPageProps) {
  const params = (await searchParams) ?? {};
  const initialStatus = isStatus(params.status) ? params.status : undefined;
  const initialStage = isStage(params.stage) ? params.stage : undefined;
  const initialQ = params.q?.trim() || undefined;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-coral">Talent Pipeline Tracker</p>
          <h1 className="text-2xl font-bold text-navy-deep">Executive Assistant - Zaragoza HQ</h1>
        </div>
        <Link href="/talent/new" className={buttonClassName("primary")}>
          Register candidate
        </Link>
      </header>

      <CandidateFilters initialStatus={initialStatus} initialStage={initialStage} initialQ={initialQ} />
      <CandidateTable />
    </div>
  );
}
