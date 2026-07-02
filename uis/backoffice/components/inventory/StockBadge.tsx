export function stockStatus(stock: number) {
  if (stock === 0) {
    return {
      label: "Out of stock",
      className: "border-coral/50 bg-white text-coral",
      dotClassName: "bg-coral",
    };
  }
  if (stock <= 10) {
    return {
      label: "Low stock",
      className: "border-coral/35 bg-coral/10 text-navy",
      dotClassName: "bg-coral",
    };
  }
  return {
    label: "Healthy",
    className: "border-teal/40 bg-teal/15 text-navy",
    dotClassName: "bg-teal",
  };
}

export function StockBadge({ stock }: { stock: number }) {
  const status = stockStatus(stock);
  return (
    <span className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs font-black ${status.className}`}>
      <span className={`h-2 w-2 shrink-0 rounded-full ${status.dotClassName}`} aria-hidden="true" />
      <span className="tabular-nums">{status.label} · {stock}</span>
    </span>
  );
}
