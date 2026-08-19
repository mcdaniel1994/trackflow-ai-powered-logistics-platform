import { useEffect, useState } from "react";
import { getWeeklyPerformance } from "@/lib/reporting/api";
import { seriesColor, useChartTheme, WAREHOUSE_LABEL, WAREHOUSE_ORDER, WAREHOUSE_SLOT } from "./palette";

const WEEKS = 6;
const VIEW_W = 720;
const VIEW_H = 280;
const PAD = { top: 16, right: 20, bottom: 44, left: 52 };

// Point value per warehouse per week; null is a genuine gap (missing week), never plotted as zero.
type WeekPoint = { week: string; values: Record<string, number | null> };

function priorMondays(weekStart: string, count: number): string[] {
  const base = new Date(`${weekStart}T00:00:00Z`);
  if (Number.isNaN(base.getTime())) return [];
  const weeks: string[] = [];
  for (let index = count - 1; index >= 0; index -= 1) {
    const day = new Date(base);
    day.setUTCDate(day.getUTCDate() - index * 7);
    weeks.push(day.toISOString().slice(0, 10));
  }
  return weeks;
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (step * magnitude >= value) return step * magnitude;
  }
  return 10 * magnitude;
}

// The only chart needing more than the single-week payload: it fetches the last 6 weeks client-side
// against the existing endpoint (no new backend route). Plots total outbound orders per warehouse.
export function TrendLineChart({ weekStart }: { weekStart: string }) {
  const theme = useChartTheme();
  const [points, setPoints] = useState<WeekPoint[] | null>(null);

  // Parent remounts via key={weekStart}, so `points` resets to null (loading) on change without a
  // synchronous setState in the effect body — only the resolved fetch updates state.
  useEffect(() => {
    let active = true;
    const weeks = priorMondays(weekStart, WEEKS);
    const load: Promise<WeekPoint[]> =
      weeks.length === 0
        ? Promise.resolve([])
        : Promise.allSettled(weeks.map((week) => getWeeklyPerformance(week))).then((results) =>
            results.map((result, index) => {
              const values: Record<string, number | null> = {};
              if (result.status === "fulfilled" && result.value.entries.length > 0) {
                for (const warehouse of WAREHOUSE_ORDER) {
                  values[warehouse] = result.value.entries
                    .filter((entry) => entry.warehouse === warehouse)
                    .reduce((sum, entry) => sum + entry.outbound_orders_count, 0);
                }
              } else {
                for (const warehouse of WAREHOUSE_ORDER) values[warehouse] = null;
              }
              return { week: weeks[index], values };
            }),
          );
    void load.then((mapped) => {
      if (active) setPoints(mapped);
    });
    return () => {
      active = false;
    };
  }, [weekStart]);

  const plotW = VIEW_W - PAD.left - PAD.right;
  const plotH = VIEW_H - PAD.top - PAD.bottom;
  const allValues = (points ?? []).flatMap((point) =>
    WAREHOUSE_ORDER.map((w) => point.values[w]).filter((v): v is number => v !== null),
  );
  const maxValue = niceMax(Math.max(0, ...allValues));
  const stepX = points && points.length > 1 ? plotW / (points.length - 1) : plotW;
  const x = (index: number) => PAD.left + index * stepX;
  const y = (value: number) => PAD.top + plotH - (value / maxValue) * plotH;

  const summary =
    points && allValues.length > 0
      ? `Weekly outbound orders per warehouse over the last ${points.length} weeks.`
      : "Weekly outbound-order trend is not available for the selected weeks.";

  return (
    <figure className="rounded-xl border border-mist bg-white p-4 shadow-sm dark:border-ink-600 dark:bg-ink-800">
      <figcaption className="mb-2 text-sm font-black text-navy-deep dark:text-neutral-100">
        Outbound orders — week over week
      </figcaption>
      {!points ? (
        <p className="rounded-lg bg-ivory p-6 text-center text-sm text-neutral-500 dark:bg-ink-700 dark:text-neutral-300">
          Loading the six-week trend…
        </p>
      ) : allValues.length === 0 ? (
        <p className="rounded-lg bg-ivory p-6 text-center text-sm text-neutral-500 dark:bg-ink-700 dark:text-neutral-300">
          No trend data for the selected weeks.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="h-auto w-full min-w-[480px]" role="img" aria-label={summary}>
              {[0, 1, 2, 3, 4].map((index) => {
                const value = (maxValue / 4) * index;
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
              {points.map((point, index) => (
                <text
                  key={point.week}
                  x={x(index)}
                  y={VIEW_H - PAD.bottom + 18}
                  textAnchor="middle"
                  className="fill-neutral-500 text-[10px] dark:fill-neutral-300"
                >
                  {point.week.slice(5)}
                </text>
              ))}
              {WAREHOUSE_ORDER.map((warehouse) => {
                const color = seriesColor(WAREHOUSE_SLOT[warehouse], theme);
                // Break the line into segments so a missing week is a gap, not an interpolated zero.
                const segments: string[] = [];
                let current: string[] = [];
                points.forEach((point, index) => {
                  const value = point.values[warehouse];
                  if (value === null) {
                    if (current.length > 1) segments.push(current.join(" "));
                    current = [];
                  } else {
                    current.push(`${x(index)},${y(value)}`);
                  }
                });
                if (current.length > 1) segments.push(current.join(" "));
                return (
                  <g key={warehouse}>
                    {segments.map((segment, segIndex) => (
                      <polyline key={segIndex} points={segment} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" />
                    ))}
                    {points.map((point, index) => {
                      const value = point.values[warehouse];
                      if (value === null) return null;
                      return (
                        <circle key={point.week} cx={x(index)} cy={y(value)} r={4} fill={color}>
                          <title>{`${WAREHOUSE_LABEL[warehouse]} · ${point.week}: ${value.toLocaleString()}`}</title>
                        </circle>
                      );
                    })}
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
