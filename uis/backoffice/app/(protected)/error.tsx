"use client";

import { RefreshCcw } from "lucide-react";

type ProtectedErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ProtectedError({ reset }: ProtectedErrorProps) {
  return (
    <section className="mx-auto max-w-2xl rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Back Office</p>
      <h2 className="mt-3 text-xl font-black text-navy-deep">This view could not load</h2>
      <p className="mt-3 text-sm text-neutral-600">
        Refresh this view or return to another Back Office area while the service recovers.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-5 inline-flex items-center gap-2 rounded-md bg-navy px-4 py-2 text-sm font-semibold text-white hover:bg-navy-deep"
      >
        <RefreshCcw className="h-4 w-4" aria-hidden="true" />
        <span>Try again</span>
      </button>
    </section>
  );
}
