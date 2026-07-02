"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { InventoryPageHeader } from "./InventoryPageHeader";
import { ProductSelector } from "./ProductSelector";
import { createInboundOrder, inventoryError, listProducts } from "@/lib/inventory/api";
import type { InventoryProduct } from "@/lib/inventory/types";

export function InboundOrderForm() {
  const searchParams = useSearchParams();
  const initialProduct = searchParams.get("product") ?? "";
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [productId, setProductId] = useState(initialProduct);
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const selected = useMemo(() => products.find((product) => String(product.id) === productId), [products, productId]);

  useEffect(() => {
    void listProducts(100, 0)
      .then((page) => setProducts(page.items))
      .catch((caught) => setError(inventoryError(caught).message));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setFieldErrors({});
    if (!selected) return setFieldErrors({ sku_id: "Select a product." });
    if (!Number.isInteger(Number(quantity)) || Number(quantity) <= 0) return setFieldErrors({ quantity: "Enter a positive whole number." });
    if (!reference.trim()) return setFieldErrors({ reference: "Enter a receipt reference." });

    setSubmitting(true);
    try {
      await createInboundOrder({
        sku_id: selected.id,
        quantity: Number(quantity),
        reference: reference.trim(),
        warehouse: selected.warehouse,
      });
      setQuantity("");
      setReference("");
      setMessage(`Received stock for ${selected.name} at ${selected.warehouse}.`);
    } catch (caught) {
      const apiError = inventoryError(caught);
      setError(apiError.message);
      setFieldErrors(apiError.fieldErrors);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-3xl">
      <InventoryPageHeader eyebrow="Inventory movement" title="Receive stock" description="Record a goods receipt. SKU and warehouse are derived from the selected product." />
      <form onSubmit={submit} className="space-y-5 rounded-xl border border-mist bg-white p-5 shadow-sm" noValidate>
        <ProductSelector products={products} value={productId} onChange={setProductId} error={fieldErrors.sku_id} />
        {selected ? <p className="rounded-lg bg-ivory p-3 text-sm text-neutral-700">Receiving into <strong>{selected.warehouse}</strong> for SKU <strong>{selected.sku}</strong>.</p> : null}
        <label className="block text-sm font-bold text-navy-deep">Receipt reference
          <input aria-label="Receipt reference" value={reference} onChange={(event) => setReference(event.target.value)} className="mt-2 w-full rounded-lg border border-mist px-3 py-2.5 font-normal" />
          {fieldErrors.reference ? <span className="mt-1 block text-xs text-rose-700">{fieldErrors.reference}</span> : null}
        </label>
        <label className="block text-sm font-bold text-navy-deep">Quantity
          <input aria-label="Quantity" type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} className="mt-2 w-full rounded-lg border border-mist px-3 py-2.5 font-normal" />
          {fieldErrors.quantity ? <span className="mt-1 block text-xs text-rose-700">{fieldErrors.quantity}</span> : null}
        </label>
        {error ? <p role="alert" className="text-sm text-rose-700">{error}</p> : null}
        {message ? <p role="status" className="text-sm font-bold text-emerald-700">{message}</p> : null}
        <button disabled={submitting} className="rounded-lg bg-navy px-4 py-2.5 text-sm font-black text-white disabled:opacity-50">{submitting ? "Saving…" : "Record receipt"}</button>
      </form>
    </section>
  );
}
