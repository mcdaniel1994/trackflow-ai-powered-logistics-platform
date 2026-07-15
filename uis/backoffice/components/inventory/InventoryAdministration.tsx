"use client";

import { Pencil, Plus, Users } from "lucide-react";
import { FormEvent, useState } from "react";
import { useAuth } from "@/lib/auth/context";
import {
  createClient,
  createProduct,
  inventoryError,
  renameClient,
  updateProductThreshold,
} from "@/lib/inventory/api";
import type { Category, InventoryClient, InventoryProduct, ProductCreateInput, Warehouse } from "@/lib/inventory/types";

type Props = {
  clients: InventoryClient[];
  products: InventoryProduct[];
  onChanged: () => Promise<void>;
};

const EMPTY_PRODUCT: ProductCreateInput = {
  name: "",
  sku: "",
  client_id: "",
  category: "fashion",
  warehouse: "LA",
  min_stock_threshold: 0,
};

export function InventoryAdministration({ clients, products, onChanged }: Props) {
  const { user } = useAuth();
  const [showProductForm, setShowProductForm] = useState(false);
  const [showClients, setShowClients] = useState(false);
  const [product, setProduct] = useState<ProductCreateInput>(EMPTY_PRODUCT);
  const [editing, setEditing] = useState<InventoryProduct | null>(null);
  const [threshold, setThreshold] = useState(0);
  const [newClientName, setNewClientName] = useState("");
  const [renameValues, setRenameValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  function beginEdit(productId: string) {
    const item = products.find((candidate) => candidate.id === Number(productId));
    if (!item) return;
    setEditing(item);
    setThreshold(item.min_stock_threshold);
    setShowProductForm(true);
    setError("");
    setMessage("");
  }

  async function submitProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      if (editing) {
        await updateProductThreshold(editing.id, threshold);
        setMessage(`Updated threshold for ${editing.name}.`);
      } else {
        await createProduct(product);
        setMessage(`Created product ${product.name}.`);
        setProduct(EMPTY_PRODUCT);
      }
      await onChanged();
      setEditing(null);
      setShowProductForm(false);
    } catch (caught) {
      setError(inventoryError(caught).message);
    } finally {
      setSaving(false);
    }
  }

  async function submitClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newClientName.trim()) return;
    setSaving(true);
    setError("");
    try {
      await createClient(newClientName.trim());
      setNewClientName("");
      setMessage("Client created.");
      await onChanged();
    } catch (caught) {
      setError(inventoryError(caught).message);
    } finally {
      setSaving(false);
    }
  }

  async function saveClientName(client: InventoryClient) {
    const displayName = (renameValues[client.client_id] ?? client.client_name).trim();
    if (!displayName || displayName === client.client_name) return;
    setSaving(true);
    setError("");
    try {
      const renamed = await renameClient(client.client_id, displayName);
      setMessage(`Renamed client to ${renamed.client_name}.`);
      await onChanged();
    } catch (caught) {
      setError(inventoryError(caught).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mb-6 rounded-xl border border-mist bg-white p-4 shadow-sm" aria-labelledby="inventory-admin-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-coral">Inventory administration</p>
          <h2 id="inventory-admin-heading" className="mt-1 text-lg font-black text-navy-deep">Clients and stock thresholds</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <select aria-label="Edit product threshold" defaultValue="" onChange={(event) => { beginEdit(event.target.value); event.target.value = ""; }} className="rounded-lg border border-mist bg-white px-3 py-2 text-sm font-black text-navy">
            <option value="" disabled>Edit product threshold</option>
            {products.map((item) => <option key={item.id} value={item.id}>Edit threshold · {item.name}</option>)}
          </select>
          <button type="button" onClick={() => { setEditing(null); setProduct(EMPTY_PRODUCT); setShowProductForm((value) => !value); }} className="inline-flex items-center gap-2 rounded-lg border border-navy bg-navy px-3 py-2 text-sm font-black text-white">
            <Plus className="h-4 w-4" aria-hidden="true" /> Add product
          </button>
          {user.role === "admin" ? (
            <button type="button" onClick={() => setShowClients((value) => !value)} className="inline-flex items-center gap-2 rounded-lg border border-mist bg-white px-3 py-2 text-sm font-black text-navy">
              <Users className="h-4 w-4" aria-hidden="true" /> Manage clients
            </button>
          ) : null}
        </div>
      </div>

      {error ? <p role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p> : null}
      {message ? <p role="status" className="mt-4 rounded-lg border border-teal/40 bg-teal/10 p-3 text-sm font-bold text-navy">{message}</p> : null}

      {showProductForm ? (
        <form onSubmit={(event) => void submitProduct(event)} className="mt-5 grid gap-4 rounded-xl border border-mist bg-ivory/50 p-4 md:grid-cols-2">
          <h3 className="md:col-span-2 text-base font-black text-navy-deep">{editing ? `Edit ${editing.name}` : "Create product"}</h3>
          {editing ? (
            <>
              <div>
                <label className="block text-xs font-black uppercase text-neutral-600">Client</label>
                <p className="mt-2 rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy" title={`Client ID: ${editing.client_id}`}>{editing.client_name}</p>
                <p className="mt-1 text-xs text-neutral-500">Client ownership is immutable after product creation.</p>
              </div>
              <label className="text-xs font-black uppercase text-neutral-600">Minimum stock threshold
                <input aria-label="Minimum stock threshold" type="number" min={0} required value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy" />
              </label>
            </>
          ) : (
            <>
              <label className="text-xs font-black uppercase text-neutral-600">Product name
                <input aria-label="Product name" required value={product.name} onChange={(event) => setProduct({ ...product, name: event.target.value })} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy" />
              </label>
              <label className="text-xs font-black uppercase text-neutral-600">SKU
                <input aria-label="SKU" required value={product.sku} onChange={(event) => setProduct({ ...product, sku: event.target.value })} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy" />
              </label>
              <label className="text-xs font-black uppercase text-neutral-600">Client
                <select aria-label="Client" required value={product.client_id} onChange={(event) => setProduct({ ...product, client_id: event.target.value })} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy">
                  <option value="">Choose client</option>
                  {clients.map((client) => <option key={client.client_id} value={client.client_id}>{client.client_name}</option>)}
                </select>
              </label>
              <label className="text-xs font-black uppercase text-neutral-600">Minimum stock threshold
                <input aria-label="Minimum stock threshold" type="number" min={0} required value={product.min_stock_threshold} onChange={(event) => setProduct({ ...product, min_stock_threshold: Number(event.target.value) })} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy" />
              </label>
              <label className="text-xs font-black uppercase text-neutral-600">Category
                <select aria-label="Category" value={product.category} onChange={(event) => setProduct({ ...product, category: event.target.value as Category })} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy">
                  <option value="fashion">Fashion</option><option value="electronics">Electronics</option><option value="cosmetics">Cosmetics</option>
                </select>
              </label>
              <label className="text-xs font-black uppercase text-neutral-600">Warehouse
                <select aria-label="Warehouse" value={product.warehouse} onChange={(event) => setProduct({ ...product, warehouse: event.target.value as Warehouse })} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy">
                  <option value="LA">Los Angeles</option><option value="ZGZ">Zaragoza</option>
                </select>
              </label>
            </>
          )}
          <div className="flex gap-2 md:col-span-2">
            <button type="submit" disabled={saving} className="rounded-lg border border-navy bg-navy px-4 py-2 text-sm font-black text-white disabled:opacity-50">{editing ? "Save threshold" : "Create product"}</button>
            <button type="button" onClick={() => { setShowProductForm(false); setEditing(null); }} className="rounded-lg border border-mist bg-white px-4 py-2 text-sm font-black text-navy">Cancel</button>
          </div>
        </form>
      ) : null}

      {user.role === "admin" && showClients ? (
        <div className="mt-5 rounded-xl border border-mist bg-ivory/50 p-4">
          <form onSubmit={(event) => void submitClient(event)} className="flex flex-wrap items-end gap-2">
            <label className="min-w-64 flex-1 text-xs font-black uppercase text-neutral-600">New client name
              <input aria-label="New client name" required value={newClientName} onChange={(event) => setNewClientName(event.target.value)} className="mt-2 block w-full rounded-lg border border-mist bg-white px-3 py-2 text-sm text-navy" />
            </label>
            <button type="submit" disabled={saving} className="rounded-lg border border-navy bg-navy px-4 py-2 text-sm font-black text-white disabled:opacity-50">Create client</button>
          </form>
          <ul className="mt-4 space-y-2">
            {clients.map((client) => (
              <li key={client.client_id} className="flex flex-wrap items-center gap-2 rounded-lg border border-mist bg-white p-3">
                <input aria-label={`Rename ${client.client_name}`} value={renameValues[client.client_id] ?? client.client_name} onChange={(event) => setRenameValues({ ...renameValues, [client.client_id]: event.target.value })} className="min-w-64 flex-1 rounded-lg border border-mist px-3 py-2 text-sm text-navy" />
                <button type="button" disabled={saving} onClick={() => void saveClientName(client)} className="inline-flex items-center gap-2 rounded-lg border border-mist bg-white px-3 py-2 text-sm font-black text-navy disabled:opacity-50"><Pencil className="h-4 w-4" aria-hidden="true" /> Save name</button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="sr-only" aria-live="polite">{products.length} products available for administration.</div>
    </section>
  );
}
