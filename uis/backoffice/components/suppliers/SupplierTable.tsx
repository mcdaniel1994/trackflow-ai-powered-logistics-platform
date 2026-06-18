"use client";

import type { KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { errorMessage, listSuppliers } from "@/lib/suppliers/api";
import {
  categoryLabel,
  countryLabel,
  isCategory,
  isCountry,
} from "@/lib/suppliers/labels";
import type { Supplier } from "@/lib/suppliers/types";
import { SupplierStatusBadge } from "@/components/suppliers/SupplierStatusBadge";
import { Spinner } from "@/components/talent/ui/Spinner";

function formatRate(supplier: Supplier) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: supplier.currency,
  }).format(supplier.rate_per_shipment);
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function SupplierTableSkeleton() {
  return (
    <tbody className="divide-y divide-neutral-200">
      {Array.from({ length: 6 }).map((_, index) => (
        <tr key={index} className="animate-pulse">
          <td className="px-4 py-4">
            <div className="h-4 w-36 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-4">
            <div className="h-4 w-24 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-4">
            <div className="h-6 w-44 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-4">
            <div className="h-4 w-24 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-4">
            <div className="h-6 w-20 rounded bg-neutral-100" />
          </td>
          <td className="px-4 py-4">
            <div className="h-6 w-28 rounded bg-neutral-100" />
          </td>
        </tr>
      ))}
    </tbody>
  );
}

export function SupplierTable() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const rawCountry = searchParams.get("country");
  const rawCategory = searchParams.get("category");
  const country = isCountry(rawCountry) ? rawCountry : undefined;
  const category = isCategory(rawCategory) ? rawCategory : undefined;

  useEffect(() => {
    let active = true;

    async function loadSuppliers() {
      setLoading(true);
      setError("");

      try {
        const result = await listSuppliers({ country, category });
        if (active) {
          setSuppliers(result);
        }
      } catch (requestError) {
        if (active) {
          setSuppliers([]);
          setError(errorMessage(requestError));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadSuppliers();

    return () => {
      active = false;
    };
  }, [country, category]);

  function openSupplier(supplier: Supplier) {
    router.push(`/suppliers/${supplier.id}`);
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, supplier: Supplier) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSupplier(supplier);
    }
  }

  return (
    <section className="min-w-0 rounded-lg border border-neutral-200 bg-white shadow-sm" aria-label="Supplier list">
      <div className="flex min-h-14 items-center justify-between border-b border-neutral-200 px-4 py-3">
        <div>
          <h2 className="text-lg font-semibold text-navy-deep">Suppliers</h2>
          <p className="text-sm text-neutral-500">
            {loading ? "Loading records" : `${suppliers.length} supplier${suppliers.length === 1 ? "" : "s"}`}
          </p>
        </div>
        {loading ? <Spinner label="Updating" /> : null}
      </div>

      {error ? (
        <div className="m-4 rounded-md border border-coral/30 bg-coral/10 p-4 text-sm text-navy-deep">
          <p className="font-semibold">Could not load suppliers.</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : null}

      <div className="max-w-full overflow-hidden">
        <table className="w-full table-fixed text-left text-sm">
          <thead className="bg-mist text-xs uppercase tracking-wide text-neutral-700">
            <tr>
              <th scope="col" className="w-[22%] px-4 py-3 font-semibold">
                Name
              </th>
              <th scope="col" className="w-[12%] px-4 py-3 font-semibold">
                Country
              </th>
              <th scope="col" className="w-[23%] px-4 py-3 font-semibold">
                Categories
              </th>
              <th scope="col" className="w-[14%] px-4 py-3 font-semibold">
                Rate
              </th>
              <th scope="col" className="w-[14%] px-3 py-3 font-semibold">
                Status
              </th>
              <th scope="col" className="w-[15%] px-3 py-3 font-semibold">
                Contact
              </th>
            </tr>
          </thead>

          {loading ? (
            <SupplierTableSkeleton />
          ) : (
            <tbody className="divide-y divide-neutral-200">
              {suppliers.map((supplier) => (
                <tr
                  key={supplier.id}
                  tabIndex={0}
                  className="cursor-pointer align-top transition-colors hover:bg-ivory focus-visible:bg-ivory"
                  aria-label={`Open ${supplier.name}`}
                  onClick={() => openSupplier(supplier)}
                  onKeyDown={(event) => handleRowKeyDown(event, supplier)}
                >
                  <td className="px-4 py-4">
                    <p className="break-words font-semibold text-navy-deep">{supplier.name}</p>
                    <p className="mt-1 text-xs font-semibold text-navy">View details</p>
                  </td>
                  <td className="px-4 py-4 text-neutral-700">{countryLabel(supplier.country)}</td>
                  <td className="px-4 py-4">
                    <div className="flex flex-wrap gap-1.5">
                      {supplier.categories.map((supplierCategory) => (
                        <span
                          key={supplierCategory}
                          className="rounded-md bg-mist px-2 py-1 text-xs font-semibold text-navy-deep"
                        >
                          {categoryLabel(supplierCategory)}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-4 text-neutral-700">
                    <span className="font-semibold text-navy-deep">{formatRate(supplier)}</span>
                    <span className="mt-1 block text-xs text-neutral-500">
                      Updated {formatDate(supplier.rate_updated_at)}
                    </span>
                  </td>
                  <td className="px-3 py-4">
                    <SupplierStatusBadge status={supplier.status} />
                  </td>
                  <td className="px-3 py-4">
                    <span
                      className={`inline-flex max-w-full rounded-md border px-2.5 py-1 text-xs font-semibold leading-tight ${
                        supplier.has_contact_email
                          ? "border-teal/40 bg-teal/10 text-navy-deep"
                          : "border-neutral-200 bg-neutral-100 text-neutral-600"
                      }`}
                    >
                      {supplier.has_contact_email ? "Contact on file" : "No contact"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>

      {!loading && !error && suppliers.length === 0 ? (
        <div className="border-t border-neutral-200 px-4 py-10 text-center">
          <p className="font-semibold text-navy-deep">No suppliers match these filters.</p>
        </div>
      ) : null}
    </section>
  );
}
