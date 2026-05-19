// Client component for the candidate detail screen. The parent page (a Server
// Component) fetches the initial data; this component owns the interactive state
// and mutations.
//
// Three things happen here:
//   1. Inline status/stage selects -> PATCH a single field (optimistic update).
//   2. The full edit form (shared <CandidateForm />) -> PATCH the whole record.
//   3. Notes panel is rendered as a sibling so it can manage its own state.
//
// Optimistic update for the selects: we flip the UI immediately, fire the PATCH,
// and roll back if the request fails. The pending spinner sits next to the
// affected control so the user knows which field is still saving.

"use client";

import Link from "next/link";
import { useState } from "react";
import { errorMessage, patchCandidate } from "@/lib/api";
import { stageLabel, stageOptions, statusLabel, statusOptions } from "@/lib/labels";
import type { Candidate, CandidatePatch, Note, Stage, Status } from "@/lib/types";
import { CandidateForm } from "@/components/CandidateForm";
import { NotesPanel } from "@/components/NotesPanel";
import { StageBadge } from "@/components/StageBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { buttonClassName } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";

type CandidateDetailViewProps = {
  initialCandidate: Candidate;
  initialNotes: Note[];
};

type SelectField = "status" | "stage";

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function ExternalLink({ href, label }: { href: string; label: string }) {
  if (!href) {
    return <span className="text-neutral-500">Not provided</span>;
  }

  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-navy underline underline-offset-2 hover:text-coral">
      {label}
    </a>
  );
}

export function CandidateDetailView({ initialCandidate, initialNotes }: CandidateDetailViewProps) {
  const [candidate, setCandidate] = useState(initialCandidate);
  const [pendingField, setPendingField] = useState<SelectField | "">("");
  const [controlError, setControlError] = useState("");
  const [controlSuccess, setControlSuccess] = useState("");

  // Optimistic update pattern for the status/stage selects:
  //   1. Stash the previous candidate so we can roll back.
  //   2. Apply the new value to local state immediately (UI feels instant).
  //   3. Fire the PATCH.
  //   4. On success, replace local state with the server's response (in case
  //      the server normalized anything we sent).
  //   5. On failure, revert to the previous candidate and surface the error.
  async function updateSelect(field: SelectField, value: Status | Stage) {
    if (candidate[field] === value) {
      return;
    }

    const previous = candidate;
    setCandidate((current) => ({ ...current, [field]: value }));
    setPendingField(field);
    setControlError("");
    setControlSuccess("");

    try {
      const patch = { [field]: value } as CandidatePatch;
      const saved = await patchCandidate(candidate.id, patch);
      setCandidate(saved);
      setControlSuccess(`${field === "status" ? "Status" : "Stage"} updated.`);
    } catch (requestError) {
      setCandidate(previous);
      setControlError(errorMessage(requestError));
    } finally {
      setPendingField("");
    }
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link href="/" className="text-sm font-semibold text-navy underline-offset-2 hover:text-coral">
            Back to list
          </Link>
          <h1 className="mt-3 text-2xl font-bold text-navy-deep">{candidate.full_name}</h1>
          <p className="mt-1 text-sm text-neutral-700">{candidate.position}</p>
        </div>
        <Link href="/candidates/new" className={buttonClassName("secondary")}>
          Register candidate
        </Link>
      </header>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-navy-deep">Candidate profile</h2>
                <p className="mt-1 text-sm text-neutral-500">Application received {formatDate(candidate.application_date)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={candidate.status} />
                <StageBadge stage={candidate.stage} />
              </div>
            </div>

            <dl className="mt-6 grid gap-4 text-sm md:grid-cols-2">
              <div>
                <dt className="font-semibold text-neutral-500">Email</dt>
                <dd className="mt-1 text-navy-deep">
                  <a href={`mailto:${candidate.email}`} className="text-navy underline-offset-2 hover:text-coral">
                    {candidate.email}
                  </a>
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-500">Phone</dt>
                <dd className="mt-1 text-navy-deep">
                  <a href={`tel:${candidate.phone}`} className="text-navy underline-offset-2 hover:text-coral">
                    {candidate.phone}
                  </a>
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-500">LinkedIn</dt>
                <dd className="mt-1">
                  <ExternalLink href={candidate.linkedin_url} label="Open profile" />
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-500">CV</dt>
                <dd className="mt-1">
                  <ExternalLink href={candidate.cv_url} label="Open CV" />
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-500">Experience</dt>
                <dd className="mt-1 text-navy-deep">{candidate.experience_years} years</dd>
              </div>
              <div>
                <dt className="font-semibold text-neutral-500">Application date</dt>
                <dd className="mt-1 text-navy-deep">{formatDate(candidate.application_date)}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-navy-deep">Edit candidate</h2>
            <p className="mt-1 text-sm text-neutral-500">Correct candidate data when a record arrives incomplete or inaccurate.</p>
            <div className="mt-5">
              <CandidateForm mode="edit" initial={candidate} onSaved={setCandidate} />
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-navy-deep">Pipeline controls</h2>
            <p className="mt-1 text-sm text-neutral-500">Changes save immediately.</p>

            <div className="mt-5 space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="detail-status" className="block text-sm font-semibold text-navy-deep">
                  Status
                </label>
                <div className="flex items-center gap-2">
                  <Select
                    id="detail-status"
                    value={candidate.status}
                    onChange={(event) => updateSelect("status", event.target.value as Status)}
                    disabled={Boolean(pendingField)}
                  >
                    {statusOptions.map((status) => (
                      <option key={status} value={status}>
                        {statusLabel(status)}
                      </option>
                    ))}
                  </Select>
                  {pendingField === "status" ? <Spinner label="Saving" /> : null}
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="detail-stage" className="block text-sm font-semibold text-navy-deep">
                  Stage
                </label>
                <div className="flex items-center gap-2">
                  <Select
                    id="detail-stage"
                    value={candidate.stage}
                    onChange={(event) => updateSelect("stage", event.target.value as Stage)}
                    disabled={Boolean(pendingField)}
                  >
                    {stageOptions.map((stage) => (
                      <option key={stage} value={stage}>
                        {stageLabel(stage)}
                      </option>
                    ))}
                  </Select>
                  {pendingField === "stage" ? <Spinner label="Saving" /> : null}
                </div>
              </div>
            </div>

            {controlError ? (
              <div className="mt-4 rounded-md border border-coral/30 bg-coral/10 p-3 text-sm text-navy-deep">
                {controlError}
              </div>
            ) : null}

            {controlSuccess ? (
              <div className="mt-4 rounded-md border border-teal/40 bg-teal/10 p-3 text-sm font-semibold text-navy-deep">
                {controlSuccess}
              </div>
            ) : null}
          </section>

          <NotesPanel candidateId={candidate.id} initialNotes={initialNotes} />
        </aside>
      </section>
    </main>
  );
}
