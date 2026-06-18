import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import { SupplierDirectoryView } from "@/components/suppliers/SupplierDirectoryView";
import { isCategory, isCountry } from "@/lib/suppliers/labels";

export const metadata: Metadata = {
  title: "Supplier Directory — TrackFlow Backoffice",
  description: "Internal supplier registry for TrackFlow carrier and warehouse operations.",
};

type SuppliersPageProps = {
  searchParams?: Promise<{
    country?: string;
    category?: string;
  }>;
};

export default async function SuppliersPage({ searchParams }: SuppliersPageProps) {
  const params = (await searchParams) ?? {};
  const initialCountry = isCountry(params.country) ? params.country : undefined;
  const initialCategory = isCategory(params.category) ? params.category : undefined;

  return (
    <AppShell>
      <SupplierDirectoryView initialCountry={initialCountry} initialCategory={initialCategory} />
    </AppShell>
  );
}
