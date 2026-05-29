import type { ReactNode } from "react";
import type { ShipmentScoreViewModel } from "@/lib/scoring";
import {
  buildInventoryRiskSnapshot,
  buildOperationsSummary,
  buildSharedDataHealth,
  buildShipmentScoreRows,
} from "@/lib/scoring";
import { StatCard } from "./StatCard";
import {
  AlertTriangle,
  BadgeCheck,
  BarChart3,
  Boxes,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Database,
  Gauge,
  MapPin,
  PackageSearch,
  Route,
  ShieldCheck,
  Truck,
  Warehouse,
  Weight,
} from "lucide-react";

function formatUsd(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value);
}

function formatKm(value: number) {
  return `${formatNumber(value)} km`;
}

function formatDays(value: number) {
  const formatted = value.toFixed(1).replace(".0", "");
  return `${formatted}d`;
}

function statusClasses(status: string) {
  if (status === "Low stock") {
    return "border-coral/35 bg-coral/10 text-navy";
  }

  if (status === "Healthy" || status === "Active") {
    return "border-teal/40 bg-teal/15 text-navy";
  }

  return "border-mist bg-ivory text-neutral-700";
}

function CapabilityPill({ label, active }: { label: string; active: boolean }) {
  const Icon = active ? CheckCircle2 : AlertTriangle;

  return (
    <span
      className={`inline-flex min-w-0 items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-bold ${
        active ? "border-teal/40 bg-teal/15 text-navy" : "border-coral/35 bg-coral/10 text-navy"
      }`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </span>
  );
}

function SectionHeading({
  eyebrow,
  title,
  description,
  icon,
  titleId,
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: ReactNode;
  titleId?: string;
}) {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-mist bg-white text-navy shadow-sm">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs font-black uppercase tracking-[0.16em] text-coral">{eyebrow}</p>
        <h2 id={titleId} className="mt-1 text-xl font-black text-navy-deep">
          {title}
        </h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-neutral-600">{description}</p>
      </div>
    </div>
  );
}

function QuoteList({ row }: { row: ShipmentScoreViewModel }) {
  return (
    <ul className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(14rem,1fr))]">
      {row.quotes.map((quote) => (
        <li
          key={`${row.shipmentId}-${quote.carrierId}`}
          className={`min-w-0 rounded-lg border px-3 py-3 text-sm transition hover:-translate-y-0.5 hover:shadow-sm ${
            quote.isBest ? "border-teal/60 bg-teal/15" : "border-mist bg-white"
          }`}
        >
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="break-words font-black leading-snug text-navy">{quote.carrierName}</p>
              <p className="mt-1 text-xs font-semibold text-neutral-600">
                {quote.reliability}% on-time / {formatDays(quote.deliveryDays)}
              </p>
            </div>
            <span className="shrink-0 whitespace-nowrap rounded-md bg-white px-2 py-1 text-xs font-black text-navy tabular-nums ring-1 ring-mist">
              {quote.score.toFixed(2)}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="shrink-0 whitespace-nowrap rounded-md bg-navy px-2.5 py-1 text-xs font-black text-white tabular-nums">
              {formatUsd(quote.cost)}
            </span>
            {quote.isBest ? (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-teal px-2.5 py-1 text-xs font-black text-navy">
                <BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />
                Best fit
              </span>
            ) : null}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <CapabilityPill label="Destination" active={quote.supportsDestination} />
            <CapabilityPill label="Priority" active={quote.supportsPriority} />
            <CapabilityPill label={`${quote.totalWeightKg.toFixed(1)} kg`} active={quote.weightFits} />
            <CapabilityPill label="Fragile" active={quote.fragileReady} />
          </div>
          <p className="mt-3 text-xs font-semibold text-neutral-500">
            Max weight {quote.maxWeightKg} kg
          </p>
        </li>
      ))}
    </ul>
  );
}

export function InventoryCarrierView() {
  const summary = buildOperationsSummary();
  const rows = buildShipmentScoreRows();
  const inventoryRisk = buildInventoryRiskSnapshot();
  const dataHealth = buildSharedDataHealth();

  return (
    <div className="space-y-8">
      <header className="flex flex-col justify-between gap-4 border-b border-mist pb-6 lg:flex-row lg:items-end">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">
            Warehouse Operations
          </p>
          <h1 className="mt-2 max-w-3xl break-words text-2xl font-black leading-tight text-navy-deep sm:text-3xl">
            Inventory + Carrier Scoring
          </h1>
          <p className="mt-3 max-w-[20rem] break-words text-neutral-600 sm:max-w-3xl">
            Pending shipments scored against active carrier lanes for today&apos;s dispatch plan.
          </p>
        </div>
        <div className="flex w-fit items-center gap-2 rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy shadow-sm">
          <ShieldCheck className="h-4 w-4 text-teal" aria-hidden="true" />
          Engagement 2 utilities live
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Operations summary">
        <StatCard
          label="Inventory Value"
          value={formatUsd(summary.totalInventoryValue)}
          detail="Active stock value across the shared product sample."
          icon={<CircleDollarSign className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Low Stock SKUs"
          value={summary.lowStockCount.toString()}
          detail="Items at or below their replenishment threshold."
          icon={<PackageSearch className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Pending / Scored"
          value={`${summary.pendingShipmentCount} / ${summary.scoredShipments}`}
          detail="Shipments pending assignment and evaluated by the scoring engine."
          icon={<Truck className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Avg Distance"
          value={formatKm(summary.averageShipmentDistanceKm)}
          detail="Mean delivery distance across the current shipment queue."
          icon={<Route className="h-5 w-5" aria-hidden="true" />}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]" aria-label="Shared operations signals">
        <article className="space-y-5">
          <SectionHeading
            eyebrow="Inventory Mix"
            title="Warehouse and category view"
            description={`Highest reliability carrier: ${summary.topReliabilityCarrier}.`}
            icon={<Warehouse className="h-5 w-5" aria-hidden="true" />}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            {summary.warehouseSummaries.map((warehouse) => (
              <div key={warehouse.warehouse} className="rounded-lg border border-mist bg-neutral-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-black text-navy">{warehouse.warehouse}</p>
                  <span className="whitespace-nowrap rounded-md bg-white px-2 py-1 text-xs font-black text-navy tabular-nums ring-1 ring-mist">
                    {warehouse.skuCount} SKUs
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs font-bold uppercase tracking-[0.12em] text-neutral-500">
                      Units
                    </dt>
                    <dd className="mt-1 font-black text-navy tabular-nums">
                      {formatNumber(warehouse.stockUnits)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-bold uppercase tracking-[0.12em] text-neutral-500">
                      Value
                    </dt>
                    <dd className="mt-1 font-black text-navy tabular-nums">
                      {formatUsd(warehouse.inventoryValue)}
                    </dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {summary.categoryCounts.map((category) => (
              <span
                key={category.category}
                className="inline-flex items-center gap-2 rounded-md border border-mist bg-ivory px-3 py-1.5 text-xs font-black text-navy"
              >
                <Boxes className="h-3.5 w-3.5 text-sky" aria-hidden="true" />
                {category.category}
                <span className="tabular-nums">{category.count}</span>
              </span>
            ))}
          </div>
        </article>

        <article className="space-y-5">
          <SectionHeading
            eyebrow="Data Health"
            title="Shared validation checks"
            description="Seeded products, shipments, and carriers run through shared validators."
            icon={<Database className="h-5 w-5" aria-hidden="true" />}
          />
          <div className="space-y-3">
            {dataHealth.map((item) => {
              const healthy = item.invalid === 0;
              const Icon = healthy ? CheckCircle2 : AlertTriangle;

              return (
                <div key={item.label} className="rounded-lg border border-mist bg-neutral-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Icon
                        className={`h-4 w-4 shrink-0 ${healthy ? "text-teal" : "text-coral"}`}
                        aria-hidden="true"
                      />
                      <p className="truncate font-black text-navy">{item.label}</p>
                    </div>
                    <span
                      className={`shrink-0 whitespace-nowrap rounded-md border px-2 py-1 text-xs font-black ${statusClasses(
                        item.status,
                      )}`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm font-semibold text-neutral-600">
                    {item.valid}/{item.total} valid / {item.invalid} invalid
                  </p>
                  {item.errors.length > 0 ? (
                    <p className="mt-2 text-xs leading-5 text-coral">{item.errors.join("; ")}</p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </article>
      </section>

      <section aria-labelledby="inventory-risk-heading">
        <SectionHeading
          eyebrow="Inventory Risk"
          title="Low-stock and fragile snapshot"
          description="Sorted by stock quantity from the shared inventory utilities."
          icon={<Gauge className="h-5 w-5" aria-hidden="true" />}
          titleId="inventory-risk-heading"
        />
        <div className="mt-4 overflow-hidden rounded-lg border border-mist bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-mist text-left text-sm">
              <thead className="bg-ivory text-xs font-black uppercase tracking-[0.12em] text-neutral-600">
                <tr>
                  <th scope="col" className="px-4 py-3">SKU</th>
                  <th scope="col" className="px-4 py-3">Category</th>
                  <th scope="col" className="px-4 py-3">Warehouse</th>
                  <th scope="col" className="px-4 py-3">Stock / Threshold</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">Value</th>
                  <th scope="col" className="px-4 py-3">Fragile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-mist">
                {inventoryRisk.map((item) => (
                  <tr key={item.sku} className="align-top transition hover:bg-neutral-50">
                    <td className="px-4 py-4">
                      <p className="font-black text-navy">{item.sku}</p>
                      <p className="mt-1 max-w-xs text-neutral-600">{item.name}</p>
                    </td>
                    <td className="px-4 py-4 font-semibold text-neutral-700">{item.category}</td>
                    <td className="px-4 py-4 text-neutral-700">{item.warehouse}</td>
                    <td className="whitespace-nowrap px-4 py-4 font-black text-navy tabular-nums">
                      {item.stockQuantity} / {item.minStockThreshold}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`whitespace-nowrap rounded-md border px-2 py-1 text-xs font-black ${statusClasses(
                          item.status,
                        )}`}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 font-black text-neutral-700 tabular-nums">
                      {formatUsd(item.inventoryValue)}
                    </td>
                    <td className="px-4 py-4">
                      <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-bold text-neutral-700">
                        {item.isFragile ? (
                          <AlertTriangle className="h-4 w-4 text-coral" aria-hidden="true" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-teal" aria-hidden="true" />
                        )}
                        {item.isFragile ? "Yes" : "No"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section aria-labelledby="shipment-table-heading">
        <SectionHeading
          eyebrow="Dispatch Queue"
          title="Carrier recommendations"
          description="Best carrier balances suitability score and delivery cost."
          icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
          titleId="shipment-table-heading"
        />
        <div className="mt-4 overflow-hidden rounded-lg border border-mist bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-mist text-left text-sm">
              <thead className="bg-ivory text-xs font-black uppercase tracking-[0.12em] text-neutral-600">
                <tr>
                  <th scope="col" className="px-4 py-3">Shipment</th>
                  <th scope="col" className="px-4 py-3">Route</th>
                  <th scope="col" className="px-4 py-3">Best carrier</th>
                  <th scope="col" className="px-4 py-3">Score</th>
                  <th scope="col" className="px-4 py-3">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-mist">
                {rows.map((row) => (
                  <tr key={row.shipmentId} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-black text-navy">{row.shipmentId}</p>
                      <p className="mt-1 text-neutral-600">{row.productName}</p>
                      <p className="mt-1 text-xs font-bold text-neutral-500">
                        {row.quantity} units / {row.priority}
                      </p>
                    </td>
                    <td className="px-4 py-4 text-neutral-700">
                      <span className="inline-flex items-start gap-2">
                        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-sky" aria-hidden="true" />
                        {row.route}
                      </span>
                    </td>
                    <td className="px-4 py-4 font-black text-navy-deep">
                      <span className="inline-flex items-center gap-2">
                        <Truck className="h-4 w-4 shrink-0 text-teal" aria-hidden="true" />
                        {row.bestCarrierName}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 font-bold text-neutral-700 tabular-nums">
                      {row.bestCarrierScore.toFixed(2)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 font-bold text-neutral-700 tabular-nums">
                      {formatUsd(row.bestCarrierCost)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section aria-labelledby="quote-breakdown-heading">
        <SectionHeading
          eyebrow="Carrier Quotes"
          title="Recommendation cards"
          description="Each quote shows score, cost, reliability, delivery speed, lane support, priority fit, weight fit, and fragile handling."
          icon={<Weight className="h-5 w-5" aria-hidden="true" />}
          titleId="quote-breakdown-heading"
        />
        <div className="mt-5 space-y-6">
          {rows.map((row) => (
            <article key={row.shipmentId} className="border-t border-mist pt-5 first:border-t-0 first:pt-0">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                <div className="min-w-0">
                  <h3 className="break-words font-black text-navy">{row.shipmentId}</h3>
                  <p className="mt-1 text-sm text-neutral-600">
                    {row.sku} / {row.quantity} units / {row.priority}
                  </p>
                </div>
                <span className="inline-flex w-fit shrink-0 items-center gap-2 rounded-md bg-ivory px-3 py-1.5 text-xs font-black text-navy ring-1 ring-mist">
                  <Clock3 className="h-3.5 w-3.5 text-sky" aria-hidden="true" />
                  {row.bestCarrierName}
                </span>
              </div>
              <QuoteList row={row} />
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
