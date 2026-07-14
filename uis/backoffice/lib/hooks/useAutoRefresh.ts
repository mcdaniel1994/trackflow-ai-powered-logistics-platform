"use client";

import { useEffect, useRef, useState } from "react";

export interface AutoRefreshState<T> {
  /** Latest successfully loaded value, or null before the first successful load. */
  data: T | null;
  /** User-facing error message from a foreground (deps-triggered) load; "" when healthy. */
  error: string;
  /** True only before the first successful load (or error): the sole time a spinner shows. */
  loading: boolean;
  /** Wall-clock time of the last successful load, for an "updated Xs ago" indicator. */
  lastUpdated: number | null;
}

/**
 * Poll a loader on an interval without flicker.
 *
 * - The first load (and any `deps` change) fetches in the background while the previous
 *   data stays on screen — stale-while-revalidate, so nothing blanks on a range change.
 * - `loading` is derived (no data and no error yet), so a spinner appears only on the very
 *   first load; state is never set synchronously inside the effect.
 * - Background ticks swallow transient errors so a blip doesn't clear a working dashboard.
 * - Polling pauses while the tab is hidden and always cleans up on unmount / deps change.
 */
export function useAutoRefresh<T>(
  loader: () => Promise<T>,
  deps: React.DependencyList,
  options: { intervalMs?: number; mapError?: (error: unknown) => string } = {},
): AutoRefreshState<T> {
  const { intervalMs = 5000, mapError } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  // Keep the newest loader without re-subscribing the interval every render.
  const loaderRef = useRef(loader);
  useEffect(() => {
    loaderRef.current = loader;
  });

  useEffect(() => {
    let active = true;

    const run = (background: boolean) => {
      loaderRef
        .current()
        .then((result) => {
          if (!active) return;
          setData(result);
          setError("");
          setLastUpdated(Date.now());
        })
        .catch((caught) => {
          // Foreground (first load / deps change) errors surface; background blips keep the
          // last good view rather than clearing it.
          if (active && !background) {
            setError(mapError ? mapError(caught) : "Something went wrong. Please try again.");
          }
        });
    };

    run(false);
    const id = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      run(true);
    }, intervalMs);

    return () => {
      active = false;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading: data === null && error === "", lastUpdated };
}
