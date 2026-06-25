"use client";

import { RefreshCcw } from "lucide-react";

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalError({ reset }: GlobalErrorProps) {
  return (
    <html lang="en">
      <body>
        <main className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-10 text-navy-deep">
          <section className="w-full max-w-md rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
            <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">TrackFlow Backoffice</p>
            <h1 className="mt-3 text-2xl font-black">Something went wrong</h1>
            <p className="mt-3 text-sm text-neutral-600">
              The Back Office could not load this view. Try again in a moment.
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
        </main>
      </body>
    </html>
  );
}
