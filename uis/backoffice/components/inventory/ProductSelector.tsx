import type { InventoryProduct } from "@/lib/inventory/types";

export function ProductSelector({
  products,
  value,
  onChange,
  error,
}: {
  products: InventoryProduct[];
  value: string;
  onChange: (value: string) => void;
  error?: string;
}) {
  return (
    <label className="block text-sm font-bold text-navy-deep">
      Product
      <select
        aria-label="Product"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-lg border border-mist bg-white px-3 py-2.5 font-normal text-neutral-800"
      >
        <option value="">Select a product</option>
        {products.map((product) => (
          <option key={product.id} value={product.id}>
            {product.name} · {product.sku} · {product.warehouse}
          </option>
        ))}
      </select>
      {error ? <span className="mt-1 block text-xs text-rose-700">{error}</span> : null}
    </label>
  );
}
