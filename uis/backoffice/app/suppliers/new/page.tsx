import type { Metadata } from "next";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { SupplierForm } from "@/components/suppliers/SupplierForm";

export const metadata: Metadata = {
  title: "Register Supplier — TrackFlow Backoffice",
  description: "Register a new supplier in the TrackFlow Supplier Directory.",
};

export default function NewSupplierPage() {
  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <Link href="/suppliers" className="text-sm font-semibold text-navy underline-offset-2 hover:text-coral">
            Back to directory
          </Link>
          <p className="mt-4 text-sm font-semibold uppercase tracking-wide text-coral">Supplier Directory</p>
          <h1 className="text-2xl font-bold text-navy-deep">Register supplier</h1>
          <p className="mt-2 text-sm text-neutral-700">
            Add a supplier for the Los Angeles or Zaragoza operations teams.
          </p>
        </header>

        <SupplierForm />
      </div>
    </AppShell>
  );
}
