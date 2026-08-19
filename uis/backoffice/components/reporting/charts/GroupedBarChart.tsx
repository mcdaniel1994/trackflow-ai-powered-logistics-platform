import type { WeeklyPerformanceEntry } from "@/lib/reporting/types";
import { seriesColor, useChartTheme, WAREHOUSE_LABEL, WAREHOUSE_ORDER, WAREHOUSE_SLOT } from "./palette";

type MetricKey = "outbound_orders_count" | "inbound_units_count";

const TOP_N = 6;
const VIEW_W = 720;
const VIEW_H = 300;
const PAD = { top: 16, right: 16, bottom: 64, left: 48 };

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const steps = [1, 2, 2.5, 5, 10];
  for (const step of steps) {
    const candidate = step * magnitude;
    if (candidate >= value) return candidate;
  }
  return 10 * magnitude;
}

type ClientRow = { client: string; values: Record<string, number> };

function aggregate(entries: WeeklyPerformanceEntry[], metric: MetricKey): ClientRow[] {
  const byClient = new Map<string, Record<string, number>>();
  for (const entry of entries) {
    const row = byClient.get(entry.client_name) ?? {};
    row[entry.warehouse] = (row[entry.warehouse] ?? 0) + (Number(entry[metric]) || 0);
    byClient.set(entry.client_name, row);
  }
  const rows = Array.from(byClient.entries()).map(([client, values]) => ({ client, values }));
  const total = (row: ClientRow) => WAREHOUSE_ORDER.reduce((sum, w) => sum + (row.values[w] ?? 0), 0);
  rows.sort((a, b) => total(b) - total(a));
  if (rows.length <= TOP_N) return rows;
  const head = rows.slice(0, TOP_N);
  const tail = rows.slice(TOP_N);
  const other: ClientRow = { client: "Other", values: {} };
  for (const row of tail) {
    for (const warehouse of WAREHOUSE_ORDER) {
      other.values[warehouse] = (other.values[warehouse] ?? 0) + (row.values[warehouse] ?? 0);
    }
  }
  return [...head, other];
}

export function GroupedBarChart({
  title,
  entries,
  metric,
}: {
  title: string;
  entries: WeeklyPerformanceEntry[];
  metric: MetricKey;
}) {
  const theme = useChartTheme();
  const rows = aggregate(entries, metric);
  const maxValue = niceMax(Math.max(0, ...rows.flatMap((row) => WAREHOUSE_ORDER.map((w) => row.values[w] ?? 0))));

  const plotW = VIEW_W - PAD.left - PAD.right;
  const plotH = VIEW_H - PAD.top - PAD.bottom;
  const groupW = rows.length ? plotW / rows.length : plotW;
  const barGap = 2;
  const barW = Math.max(2, (groupW * 0.62) / WAREHOUSE_ORDER.length - barGap);
  const y = (value: number) => PAD.top + plotH - (value / maxValue) * plotH;
  const gridLines = 4;

  return (
    <figure className="rounded-xl border border-mist bg-white p-4 shadow-sm dark:border-ink-600 dark:bg-ink-800">
      <figcaption className="mb-2 text-sm font-black text-navy-deep dark:text-neutral-100">{title}</figcaption>
      {rows.length === 0 ? (
        <p className="rounded-lg bg-ivory p-6 text-center text-sm text-neutral-500 dark:bg-ink-700 dark:text-neutral-300">
          No client activity for this week.
        </p>
      ) : (
        <>
          {/* Same data is present in the retained precise table below, so the SVG is decorative. */}
          <div className="overflow-x-auto">
            <svg
              viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
              className="h-auto w-full min-w-[520px]"
              role="presentation"
              aria-hidden="true"
            >
              {Array.from({ length: gridLines + 1 }, (_, index) => {
                const value = (maxValue / gridLines) * index;
                const gy = y(value);
                return (
                  <g key={index}>
                    <line x1={PAD.left} x2={VIEW_W - PAD.right} y1={gy} y2={gy} className="stroke-mist dark:stroke-ink-600" strokeWidth={1} />
                    <text x={PAD.left - 8} y={gy + 4} textAnchor="end" className="fill-neutral-400 text-[10px]">
                      {value.toLocaleString()}
                    </text>
                  </g>
                );
              })}
              {rows.map((row, rowIndex) => {
                const groupX = PAD.left + rowIndex * groupW;
                const clusterW = WAREHOUSE_ORDER.length * barW + (WAREHOUSE_ORDER.length - 1) * barGap;
                const startX = groupX + (groupW - clusterW) / 2;
                return (
                  <g key={row.client}>
                    {WAREHOUSE_ORDER.map((warehouse, seriesIndex) => {
                      const value = row.values[warehouse] ?? 0;
                      const barX = startX + seriesIndex * (barW + barGap);
                      const barY = y(value);
                      const barH = PAD.top + plotH - barY;
                      return (
                        <rect
                          key={warehouse}
                          x={barX}
                          y={barY}
                          width={barW}
                          height={Math.max(0, barH)}
                          rx={4}
                          fill={seriesColor(WAREHOUSE_SLOT[warehouse], theme)}
                        >
                          <title>{`${row.client} — ${WAREHOUSE_LABEL[warehouse]}: ${value.toLocaleString()}`}</title>
                        </rect>
                      );
                    })}
                    <text
                      x={groupX + groupW / 2}
                      y={VIEW_H - PAD.bottom + 16}
                      textAnchor="middle"
                      className="fill-neutral-500 text-[10px] dark:fill-neutral-300"
                    >
                      {row.client.length > 14 ? `${row.client.slice(0, 13)}…` : row.client}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <ul className="mt-3 flex flex-wrap gap-4">
            {WAREHOUSE_ORDER.map((warehouse) => (
              <li key={warehouse} className="flex items-center gap-2 text-xs font-bold text-neutral-600 dark:text-neutral-300">
                <span
                  className="inline-block h-3 w-3 rounded-sm"
                  style={{ backgroundColor: seriesColor(WAREHOUSE_SLOT[warehouse], theme) }}
                  aria-hidden="true"
                />
                {WAREHOUSE_LABEL[warehouse]}
              </li>
            ))}
          </ul>
        </>
      )}
    </figure>
  );
}
