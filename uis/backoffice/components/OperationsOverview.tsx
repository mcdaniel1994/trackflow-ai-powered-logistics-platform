"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowDownToLine, ArrowRight, BarChart3, PackageMinus, PackagePlus, Truck } from "lucide-react";
import { LiveIndicator } from "@/components/telemetry/LiveIndicator";
import { StatCard } from "@/components/StatCard";
import { useAutoRefresh } from "@/lib/hooks/useAutoRefresh";
import { listMovements } from "@/lib/inventory/api";
import type { StockMovement } from "@/lib/inventory/types";
import {
  defaultRange,
  getDispatchMetrics,
  getReceivingMetrics,
  getStockLossMetrics,
  telemetryError,
} from "@/lib/telemetry/api";
import type { DispatchMetrics, ReceivingMetrics, StockLossMetrics } from "@/lib/telemetry/types";

interface OverviewData {
  dispatch: DispatchMetrics;
  receiving: ReceivingMetrics;
  loss: StockLossMetrics;
  movements: StockMovement[];
}

function relativeTime(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function movementLabel(movement: StockMovement): { text: string; tone: string; icon: typeof Truck } {
  if (movement.movement_type === "inbound") {
    return { text: "Received", tone: "text-teal", icon: ArrowDownToLine };
  }
  if (movement.exit_type === "loss") {
    return { text: "Stock loss", tone: "text-coral", icon: PackageMinus };
  }
  return { text: "Dispatched", tone: "text-navy", icon: Truck };
}

export function OperationsOverview() {
  const range = defaultRange();
  const { data, error, loading, lastUpdated } = useAutoRefresh<OverviewData>(
    () =>
      Promise.all([
        getDispatchMetrics(range),
        getReceivingMetrics(range),
        getStockLossMetrics(range),
        listMovements(8, 0),
      ]).then(([dispatch, receiving, loss, movements]) => ({
        dispatch,
        receiving,
        loss,
        movements: movements.items,
      })),
    [range.from, range.to],
    { mapError: (caught) => telemetryError(caught).message },
  );

  // Tick once a second so relative "Xs ago" labels stay fresh without re-fetching.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const totalDispatched = data?.dispatch.rows.reduce((sum, row) => sum + row.dispatched, 0) ?? 0;
  const totalReceived = data?.receiving.rows.reduce((sum, row) => sum + row.count, 0) ?? 0;
  const totalLossUnits = data?.loss.rows.reduce((sum, row) => sum + row.units, 0) ?? 0;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-8">
      <header className="border-b border-mist pb-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Warehouse Operations</p>
            <h1 className="mt-2 text-2xl font-black leading-tight text-navy-deep sm:text-3xl">Operations Overview</h1>
            <p className="mt-3 max-w-3xl text-neutral-600">
              Live fulfilment activity across Los Angeles and Zaragoza, read from the inventory system of
              record. Figures refresh automatically.
            </p>
          </div>
          <LiveIndicator lastUpdated={lastUpdated} />
        </div>
      </header>

      {error ? (
        <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}
        </p>
      ) : null}
      {loading && !data ? <p className="text-sm text-neutral-600">Loading live operations…</p> : null}

      {data ? (
        <>
          <section className="grid gap-4 sm:grid-cols-3" aria-label="Exact fulfilment totals (last 7 days)">
            <StatCard
              label="Dispatched (7d)"
              value={String(totalDispatched)}
              detail="Committed dispatch movements, both warehouses"
              icon={<Truck className="h-5 w-5" aria-hidden="true" />}
            />
            <StatCard
              label="Received (7d)"
              value={String(totalReceived)}
              detail="Committed receiving movements, both warehouses"
              icon={<PackagePlus className="h-5 w-5" aria-hidden="true" />}
            />
            <StatCard
              label="Stock loss units (7d)"
              value={String(totalLossUnits)}
              detail="Units written off as loss in the window"
              icon={<PackageMinus className="h-5 w-5" aria-hidden="true" />}
            />
          </section>

          <section aria-labelledby="recent-activity-heading">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 id="recent-activity-heading" className="text-lg font-black text-navy-deep">
                Recent activity
              </h2>
              <Link
                href="/backoffice/operations/fulfilment"
                className="inline-flex items-center gap-1 text-sm font-bold text-navy hover:text-coral"
              >
                Fulfilment details <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
            <ul className="divide-y divide-mist overflow-hidden rounded-xl border border-mist bg-white shadow-sm">
              {data.movements.map((movement) => {
                const label = movementLabel(movement);
                const Icon = label.icon;
                return (
                  <li key={`${movement.movement_type}-${movement.id}`} className="flex items-center gap-3 px-4 py-3">
                    <Icon className={`h-4 w-4 shrink-0 ${label.tone}`} aria-hidden="true" />
                    <span className={`w-24 shrink-0 text-sm font-black ${label.tone}`}>{label.text}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-neutral-700">
                      <span className="font-bold text-navy-deep tabular-nums">{movement.quantity}</span> ×{" "}
                      {movement.sku.sku}
                    </span>
                    <span className="shrink-0 rounded-md bg-ivory px-2 py-1 text-xs font-black text-navy">
                      {movement.warehouse}
                    </span>
                    <span className="w-20 shrink-0 text-right text-xs text-neutral-500">
                      {relativeTime(movement.created_at, now)}
                    </span>
                  </li>
                );
              })}
              {!data.movements.length ? (
                <li className="px-4 py-6 text-sm text-neutral-600">No recent movements yet.</li>
              ) : null}
            </ul>
          </section>

          <section className="flex flex-wrap gap-3">
            <Link
              href="/backoffice/operations/stock-loss"
              className="inline-flex items-center gap-2 rounded-lg border border-mist bg-white px-4 py-2 text-sm font-black text-navy transition hover:bg-ivory"
            >
              Stock loss details
            </Link>
            <Link
              href="/backoffice/inventory/products"
              className="inline-flex items-center gap-2 rounded-lg border border-navy bg-navy px-4 py-2 text-sm font-black text-white transition hover:bg-navy-deep"
            >
              <BarChart3 className="h-4 w-4" aria-hidden="true" /> Inventory Management
            </Link>
            <Link
              href="/backoffice/telemetry/security"
              className="inline-flex items-center gap-2 rounded-lg border border-mist bg-white px-4 py-2 text-sm font-black text-navy transition hover:bg-ivory"
            >
              Technical security telemetry
            </Link>
          </section>
        </>
      ) : null}
    </div>
  );
}
