"use client";

import Link from "next/link";
import { PackageMinus, PackagePlus } from "lucide-react";
import { useEffect, useState } from "react";
import { InventoryPageHeader } from "./InventoryPageHeader";
import { StockBadge } from "./StockBadge";
import { inventoryError, listProducts } from "@/lib/inventory/api";
import type { InventoryProduct, Page } from "@/lib/inventory/types";

const PAGE_SIZE = 20;

export function InventoryProductsView() {
  const [page, setPage] = useState<Page<InventoryProduct> | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void listProducts(PAGE_SIZE, offset)
      .then((result) => active && setPage(result))
      .catch((caught) => active && setError(inventoryError(caught).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [offset]);

  function changePage(nextOffset: number) {
    setLoading(true);
    setError("");
    setOffset(nextOffset);
  }

  return (
    <section className="mx-auto w-full max-w-7xl">
      <InventoryPageHeader
        eyebrow="Inventory management"
        title="Products and stock"
        description="Review computed warehouse stock. Stock changes only through inbound receipts, dispatches, and confirmed losses."
      />
      {error ? <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
      {loading ? <p className="text-sm text-neutral-600">Loading products…</p> : null}
      {!loading && page ? (
        <>
          <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                <tr>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Client</th>
                  <th className="px-4 py-3">Warehouse</th>
                  <th className="px-4 py-3">Stock</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-mist">
                {page.items.map((product) => (
                  <tr key={product.id}>
                    <td className="px-4 py-4">
                      <p className="font-black text-navy-deep">{product.name}</p>
                      <p className="mt-1 font-mono text-xs text-neutral-500">{product.sku}</p>
                    </td>
                    <td className="px-4 py-4 text-neutral-700">{product.client_name}</td>
                    <td className="px-4 py-4 font-bold text-navy">{product.warehouse}</td>
                    <td className="px-4 py-4"><StockBadge stock={product.current_stock} /></td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-2">
                        <Link
                          href={`/backoffice/inventory/orders/inbound?product=${product.id}`}
                          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-teal/50 bg-teal/10 px-2.5 py-1.5 text-xs font-black text-navy transition hover:border-teal hover:bg-teal/20"
                        >
                          <PackagePlus className="h-3.5 w-3.5 text-teal" aria-hidden="true" />
                          Receive
                        </Link>
                        <Link
                          href={`/backoffice/inventory/orders/outbound?product=${product.id}`}
                          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-coral/45 bg-coral/10 px-2.5 py-1.5 text-xs font-black text-navy transition hover:border-coral hover:bg-coral/20"
                        >
                          <PackageMinus className="h-3.5 w-3.5 text-coral" aria-hidden="true" />
                          Dispatch / loss
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!page.items.length ? <p className="p-6 text-sm text-neutral-600">No products found.</p> : null}
          </div>
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-neutral-600">Showing {page.items.length ? offset + 1 : 0}–{Math.min(offset + page.items.length, page.total)} of {page.total}</p>
            <div className="flex gap-2">
              <button type="button" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))} className="rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy disabled:opacity-40">Previous</button>
              <button type="button" disabled={offset + PAGE_SIZE >= page.total} onClick={() => changePage(offset + PAGE_SIZE)} className="rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy disabled:opacity-40">Next</button>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
