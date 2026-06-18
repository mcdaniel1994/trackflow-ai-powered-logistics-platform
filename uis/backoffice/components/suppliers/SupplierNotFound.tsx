import Link from "next/link";
import { buttonClassName } from "@/components/talent/ui/Button";

export function SupplierNotFound() {
  return (
    <div className="mx-auto max-w-3xl py-10">
      <div className="rounded-lg border border-neutral-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-coral">Supplier not found</p>
        <h1 className="mt-2 text-2xl font-bold text-navy-deep">This supplier is not in the directory.</h1>
        <p className="mt-3 text-sm text-neutral-700">
          The record may have been removed, or the link may be incorrect.
        </p>
        <Link href="/suppliers" className={buttonClassName("primary", "mt-6")}>
          Back to directory
        </Link>
      </div>
    </div>
  );
}
