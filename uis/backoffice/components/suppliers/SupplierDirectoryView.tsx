"use client";

import Link from "next/link";
import { SupplierFilters } from "@/components/suppliers/SupplierFilters";
import { SupplierTable } from "@/components/suppliers/SupplierTable";
import { buttonClassName } from "@/components/talent/ui/Button";
import type { Country, SupplierCategory } from "@/lib/suppliers/types";

type SupplierDirectoryViewProps = {
  initialCountry?: Country;
  initialCategory?: SupplierCategory;
};

export function SupplierDirectoryView({ initialCountry, initialCategory }: SupplierDirectoryViewProps) {
  return (
    <div className="min-w-0 space-y-6">
      <header className="flex flex-col justify-between gap-4 border-b border-mist pb-6 lg:flex-row lg:items-end">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">
            Carrier Operations
          </p>
          <h1 className="mt-2 max-w-3xl break-words text-2xl font-black leading-tight text-navy-deep sm:text-3xl">
            Supplier Directory
          </h1>
          <p className="mt-3 max-w-[20rem] break-words text-neutral-600 sm:max-w-3xl">
            Centralized supplier records for the Los Angeles and Zaragoza operations teams.
          </p>
        </div>
        <Link href="/suppliers/new" className={buttonClassName("primary")}>
          Register supplier
        </Link>
      </header>

      <SupplierFilters initialCountry={initialCountry} initialCategory={initialCategory} />

      <div className="grid min-w-0 gap-6">
        <SupplierTable />
      </div>
    </div>
  );
}
