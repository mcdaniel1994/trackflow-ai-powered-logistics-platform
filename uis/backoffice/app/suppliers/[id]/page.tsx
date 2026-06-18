import type { Metadata } from "next";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { SupplierDetailView } from "@/components/suppliers/SupplierDetailView";
import { SupplierNotFound } from "@/components/suppliers/SupplierNotFound";
import { buttonClassName } from "@/components/talent/ui/Button";
import { errorMessage, getSupplier, isNotFoundError } from "@/lib/suppliers/api";
import type { Supplier } from "@/lib/suppliers/types";

export const metadata: Metadata = {
  title: "Supplier Detail — TrackFlow Backoffice",
  description: "Supplier detail, rate controls, status controls, and contact reveal.",
};

type SupplierPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function SupplierPage({ params }: SupplierPageProps) {
  const { id } = await params;

  let supplier: Supplier | undefined;
  let requestError: unknown;

  try {
    supplier = await getSupplier(id);
  } catch (caught) {
    requestError = caught;
  }

  if (supplier) {
    return (
      <AppShell>
        <SupplierDetailView initialSupplier={supplier} />
      </AppShell>
    );
  }

  if (isNotFoundError(requestError)) {
    return (
      <AppShell>
        <SupplierNotFound />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl py-10">
        <div className="rounded-lg border border-coral/30 bg-white p-8 text-center shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-wide text-coral">Could not load supplier</p>
          <h1 className="mt-2 text-2xl font-bold text-navy-deep">The directory could not reach this record.</h1>
          <p className="mt-3 text-sm text-neutral-700">{errorMessage(requestError)}</p>
          <Link href="/suppliers" className={buttonClassName("primary", "mt-6")}>
            Back to directory
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
