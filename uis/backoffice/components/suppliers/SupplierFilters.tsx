"use client";

import { useCallback, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  categoryLabel,
  categoryOptions,
  countryLabel,
  countryOptions,
  isCategory,
  isCountry,
} from "@/lib/suppliers/labels";
import { Button } from "@/components/talent/ui/Button";
import { Select } from "@/components/talent/ui/Select";
import type { Country, SupplierCategory } from "@/lib/suppliers/types";

type SupplierFiltersProps = {
  initialCountry?: Country;
  initialCategory?: SupplierCategory;
};

export function SupplierFilters({ initialCountry, initialCategory }: SupplierFiltersProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const rawCountry = searchParams.get("country");
  const rawCategory = searchParams.get("category");
  const currentCountry = isCountry(rawCountry) ? rawCountry : initialCountry ?? "";
  const currentCategory = isCategory(rawCategory) ? rawCategory : initialCategory ?? "";

  const replaceParam = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());

      if (value) {
        params.set(name, value);
      } else {
        params.delete(name);
      }

      const query = params.toString();
      startTransition(() => {
        router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
      });
    },
    [pathname, router, searchParams],
  );

  const hasFilters = Boolean(currentCountry || currentCategory);

  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm" aria-label="Supplier filters">
      <div className="grid gap-4 md:grid-cols-[220px_260px_auto] md:items-end">
        <div className="space-y-1.5">
          <label htmlFor="supplier-country-filter" className="block text-sm font-semibold text-navy-deep">
            Country
          </label>
          <Select
            id="supplier-country-filter"
            value={currentCountry}
            onChange={(event) => replaceParam("country", event.target.value)}
            disabled={isPending}
          >
            <option value="">All countries</option>
            {countryOptions.map((country) => (
              <option key={country} value={country}>
                {countryLabel(country)}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="supplier-category-filter" className="block text-sm font-semibold text-navy-deep">
            Category
          </label>
          <Select
            id="supplier-category-filter"
            value={currentCategory}
            onChange={(event) => replaceParam("category", event.target.value)}
            disabled={isPending}
          >
            <option value="">All categories</option>
            {categoryOptions.map((category) => (
              <option key={category} value={category}>
                {categoryLabel(category)}
              </option>
            ))}
          </Select>
        </div>

        <Button
          variant="secondary"
          onClick={() => {
            startTransition(() => {
              router.replace(pathname, { scroll: false });
            });
          }}
          disabled={!hasFilters || isPending}
        >
          Clear
        </Button>
      </div>
    </section>
  );
}
