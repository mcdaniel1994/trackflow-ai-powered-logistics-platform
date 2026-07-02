"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { InventoryPageHeader } from "./InventoryPageHeader";
import { ProductSelector } from "./ProductSelector";
import { StockBadge } from "./StockBadge";
import { createOutboundOrder, getProduct, inventoryError, listProducts } from "@/lib/inventory/api";
import type { ExitType, InventoryProduct } from "@/lib/inventory/types";

export function OutboundOrderForm() {
  const searchParams = useSearchParams();
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [productId, setProductId] = useState(searchParams.get("product") ?? "");
  const [selected, setSelected] = useState<InventoryProduct | null>(null);
  const [quantity, setQuantity] = useState("");
  const [exitType, setExitType] = useState<ExitType>("dispatch");
  const [tracking, setTracking] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [quantityError, setQuantityError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const exceedsStock = useMemo(() => selected !== null && Number(quantity) > selected.current_stock, [quantity, selected]);

  useEffect(() => {
    void listProducts(100, 0)
      .then((page) => setProducts(page.items))
      .catch((caught) => setError(inventoryError(caught).message));
  }, []);

  useEffect(() => {
    if (!productId) return;
    void getProduct(Number(productId))
      .then(setSelected)
      .catch((caught) => setError(inventoryError(caught).message));
  }, [productId]);

  function selectProduct(value: string) {
    setSelected(null);
    setQuantityError("");
    setError("");
    setProductId(value);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setQuantityError("");
    if (!selected) return setError("Select a product.");
    if (!Number.isInteger(Number(quantity)) || Number(quantity) <= 0) return setQuantityError("Enter a positive whole number.");
    if (exceedsStock) return setQuantityError(`Only ${selected.current_stock} units are currently available.`);
    if (exitType === "dispatch" && !tracking.trim()) return setError("A tracking number is required for dispatch.");

    setSubmitting(true);
    try {
      await createOutboundOrder({
        sku_id: selected.id,
        quantity: Number(quantity),
        exit_type: exitType,
        tracking_number: exitType === "dispatch" ? tracking.trim() : null,
        warehouse: selected.warehouse,
      });
      const refreshed = await getProduct(selected.id);
      setSelected(refreshed);
      setQuantity("");
      setTracking("");
      setMessage(`${exitType === "dispatch" ? "Dispatch" : "Loss"} recorded for ${selected.name}.`);
    } catch (caught) {
      const apiError = inventoryError(caught);
      setError(apiError.message);
      // Central API's authoritative insufficient-stock 400 stays beside quantity.
      if (apiError.status === 400 && apiError.message.startsWith("Insufficient stock")) setQuantityError(apiError.message);
      if (apiError.fieldErrors.quantity) setQuantityError(apiError.fieldErrors.quantity);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-3xl">
      <InventoryPageHeader eyebrow="Inventory movement" title="Dispatch or record loss" description="Current stock is refreshed for the selected product. Central API remains authoritative at submission." />
      <form onSubmit={submit} className="space-y-5 rounded-xl border border-mist bg-white p-5 shadow-sm" noValidate>
        <ProductSelector products={products} value={productId} onChange={selectProduct} />
        {selected ? <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-ivory p-3 text-sm"><span><strong>{selected.sku}</strong> · {selected.warehouse}</span><StockBadge stock={selected.current_stock} /></div> : null}
        <label className="block text-sm font-bold text-navy-deep">Movement type
          <select aria-label="Movement type" value={exitType} onChange={(event) => { setExitType(event.target.value as ExitType); if (event.target.value === "loss") setTracking(""); }} className="mt-2 w-full rounded-lg border border-mist bg-white px-3 py-2.5 font-normal">
            <option value="dispatch">Dispatch</option>
            <option value="loss">Confirmed loss</option>
          </select>
        </label>
        {exitType === "dispatch" ? <label className="block text-sm font-bold text-navy-deep">Tracking number
          <input aria-label="Tracking number" value={tracking} onChange={(event) => setTracking(event.target.value)} className="mt-2 w-full rounded-lg border border-mist px-3 py-2.5 font-normal" />
        </label> : null}
        <label className="block text-sm font-bold text-navy-deep">Quantity
          <input aria-label="Quantity" type="number" min="1" step="1" value={quantity} onChange={(event) => { setQuantity(event.target.value); setQuantityError(""); }} className="mt-2 w-full rounded-lg border border-mist px-3 py-2.5 font-normal" />
          {exceedsStock ? <span className="mt-1 block text-xs font-bold text-amber-800">Requested quantity exceeds displayed stock.</span> : null}
          {quantityError ? <span role="alert" className="mt-1 block text-xs text-rose-700">{quantityError}</span> : null}
        </label>
        {error && !quantityError ? <p role="alert" className="text-sm text-rose-700">{error}</p> : null}
        {message ? <p role="status" className="text-sm font-bold text-emerald-700">{message}</p> : null}
        <button disabled={submitting || exceedsStock} className="rounded-lg bg-navy px-4 py-2.5 text-sm font-black text-white disabled:opacity-50">{submitting ? "Saving…" : "Record movement"}</button>
      </form>
    </section>
  );
}
