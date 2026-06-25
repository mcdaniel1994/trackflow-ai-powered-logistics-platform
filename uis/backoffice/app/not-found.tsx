import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50 px-4 py-10 text-navy-deep">
      <section className="w-full max-w-md rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">TrackFlow Backoffice</p>
        <h1 className="mt-3 text-2xl font-black">Page not found</h1>
        <p className="mt-3 text-sm text-neutral-600">The Back Office page you requested does not exist.</p>
        <Link
          href="/"
          className="mt-5 inline-flex items-center gap-2 rounded-md bg-navy px-4 py-2 text-sm font-semibold text-white hover:bg-navy-deep"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          <span>Back to dashboard</span>
        </Link>
      </section>
    </main>
  );
}
