import type { WeeklyPerformanceEntry } from "@/lib/reporting/types";
import { seriesColor, useChartTheme } from "./palette";

const VIEW_W = 720;
const ROW_H = 30;
const PAD = { top: 8, right: 56, bottom: 8, left: 140 };

// Per-client discrepancy rate (mean across the client's warehouses), sorted worst-first. Rate is a
// ratio, so it is labelled as a percentage on a single axis — never a second measure on a second axis.
function aggregate(entries: WeeklyPerformanceEntry[]): { client: string; rate: number }[] {
  const byClient = new Map<string, number[]>();
  for (const entry of entries) {
    const rates = byClient.get(entry.client_name) ?? [];
    rates.push(entry.discrepancy_rate);
    byClient.set(entry.client_name, rates);
  }
  return Array.from(byClient.entries())
    .map(([client, rates]) => ({ client, rate: rates.reduce((a, b) => a + b, 0) / rates.length }))
    .sort((a, b) => b.rate - a.rate);
}

function formatPct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

export function DiscrepancyRateChart({ entries }: { entries: WeeklyPerformanceEntry[] }) {
  const theme = useChartTheme();
  const rows = aggregate(entries);
  const maxRate = Math.max(0.0001, ...rows.map((row) => row.rate));
  const viewH = PAD.top + PAD.bottom + rows.length * ROW_H;
  const plotW = VIEW_W - PAD.left - PAD.right;
  const color = seriesColor(0, theme);

  return (
    <figure className="rounded-xl border border-mist bg-white p-4 shadow-sm dark:border-ink-600 dark:bg-ink-800">
      <figcaption className="mb-2 text-sm font-black text-navy-deep dark:text-neutral-100">
        Discrepancy rate by client
      </figcaption>
      {rows.length === 0 ? (
        <p className="rounded-lg bg-ivory p-6 text-center text-sm text-neutral-500 dark:bg-ink-700 dark:text-neutral-300">
          No client activity for this week.
        </p>
      ) : (
        <div className="overflow-x-auto">
          {/* Same rates are present in the retained table below, so the SVG is decorative. */}
          <svg
            viewBox={`0 0 ${VIEW_W} ${viewH}`}
            className="h-auto w-full min-w-[480px]"
            role="presentation"
            aria-hidden="true"
          >
            {rows.map((row, index) => {
              const rowY = PAD.top + index * ROW_H;
              const barW = (row.rate / maxRate) * plotW;
              return (
                <g key={row.client}>
                  <text
                    x={PAD.left - 8}
                    y={rowY + ROW_H / 2 + 4}
                    textAnchor="end"
                    className="fill-neutral-600 text-[11px] dark:fill-neutral-300"
                  >
                    {row.client.length > 18 ? `${row.client.slice(0, 17)}…` : row.client}
                  </text>
                  <rect
                    x={PAD.left}
                    y={rowY + 6}
                    width={Math.max(2, barW)}
                    height={ROW_H - 12}
                    rx={4}
                    fill={color}
                  >
                    <title>{`${row.client}: ${formatPct(row.rate)}`}</title>
                  </rect>
                  <text
                    x={PAD.left + Math.max(2, barW) + 6}
                    y={rowY + ROW_H / 2 + 4}
                    className="fill-neutral-600 text-[11px] font-bold tabular-nums dark:fill-neutral-300"
                  >
                    {formatPct(row.rate)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </figure>
  );
}
