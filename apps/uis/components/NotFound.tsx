// Friendly not-found view used when a candidate ID in the URL doesn't exist
// (or returns 422 from this mock API). Rendered by the detail page's catch
// block when `isNotFoundError(err)` matches. We don't use Next's built-in
// `notFound()` here because we want a branded panel with a "Back to list"
// affordance rather than a generic 404 page.

import Link from "next/link";
import { buttonClassName } from "@/components/ui/Button";

export function NotFound() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <div className="rounded-lg border border-neutral-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-coral">Candidate not found</p>
        <h1 className="mt-2 text-2xl font-bold text-navy-deep">This candidate is not in the tracker.</h1>
        <p className="mt-3 text-sm text-neutral-700">
          The record may have been removed, or the link may be incorrect.
        </p>
        <Link href="/" className={buttonClassName("primary", "mt-6")}>
          Back to list
        </Link>
      </div>
    </main>
  );
}
