"use client";

import { useEffect, useState } from "react";
import { InventoryPageHeader } from "./InventoryPageHeader";
import { inventoryError, listMovements } from "@/lib/inventory/api";
import type { Page, StockMovement } from "@/lib/inventory/types";

const PAGE_SIZE = 20;

function movementLabel(movement: StockMovement) {
  if (movement.movement_type === "inbound") return "Inbound receipt";
  return movement.exit_type === "loss" ? "Confirmed loss" : "Dispatch";
}

export function InventoryHistoryView() {
  const [page, setPage] = useState<Page<StockMovement> | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void listMovements(PAGE_SIZE, offset)
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
      <InventoryPageHeader eyebrow="Inventory audit" title="Movement history" description="Reverse-chronological receipts, dispatches, and losses with the raw Identity UUID retained for audit traceability." />
      {error ? <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
      {loading ? <p className="text-sm text-neutral-600">Loading movement history…</p> : null}
      {!loading && page ? (
        <>
          <div className="overflow-x-auto rounded-xl border border-mist bg-white shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-ivory text-xs uppercase tracking-wide text-neutral-600">
                <tr>
                  <th className="px-4 py-3">Date</th><th className="px-4 py-3">Product</th><th className="px-4 py-3">Movement</th><th className="px-4 py-3">Quantity</th><th className="px-4 py-3">Warehouse</th><th className="px-4 py-3">Reference</th><th className="px-4 py-3">User UUID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-mist">
                {page.items.map((movement) => (
                  <tr key={`${movement.movement_type}-${movement.id}`}>
                    <td className="whitespace-nowrap px-4 py-4 text-neutral-600">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(movement.created_at))}</td>
                    <td className="px-4 py-4"><p className="font-black text-navy-deep">{movement.sku.name}</p><p className="font-mono text-xs text-neutral-500">{movement.sku.sku}</p></td>
                    <td className="px-4 py-4 font-bold text-navy">{movementLabel(movement)}</td>
                    <td className="px-4 py-4">{movement.quantity}</td>
                    <td className="px-4 py-4 font-bold">{movement.warehouse}</td>
                    <td className="px-4 py-4 text-neutral-600">{movement.reference ?? movement.tracking_number ?? "—"}</td>
                    <td className="px-4 py-4 font-mono text-xs text-neutral-600">{movement.user_uuid}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!page.items.length ? <p className="p-6 text-sm text-neutral-600">No inventory movements found.</p> : null}
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
