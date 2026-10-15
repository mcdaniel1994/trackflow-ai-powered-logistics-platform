"use client";

import { useEffect, useRef, useState } from "react";

export interface PollingResource<T = unknown> {
  data: T | null;
  error: string;
  loading: boolean;
  lastSuccess: number | null;
  retrying: boolean;
}

const initial = { data: null, error: "", loading: true, lastSuccess: null, retrying: false };

function isTransient(error: unknown): boolean {
  if (error instanceof TypeError) return true; // Browser fetch network failure.
  return !!error && typeof error === "object" && "status" in error &&
    [502, 503, 504].includes(Number(error.status));
}

/** Independent, read-only polling. A scope change immediately hides the previous range's data. */
export function useResourcePolling<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  scope: string,
  mapError: (error: unknown) => string,
): PollingResource<T> {
  const [state, setState] = useState<PollingResource<T> & { scope: string }>({ ...initial, scope });
  const callbacks = useRef({ loader, mapError });
  useEffect(() => { callbacks.current = { loader, mapError }; });

  useEffect(() => {
    let active = true;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;
    let refreshOnSettle = false;

    const run = async () => {
      if (!active || document.hidden || controller) return;
      const request = new AbortController();
      controller = request;
      let timedOut = false;
      // The BFF normally returns its own 15-second timeout. Bound a stalled browser request too.
      const deadline = setTimeout(() => { timedOut = true; request.abort(); }, 20_000);
      let delay: number | null = null;
      try {
        const data = await callbacks.current.loader(request.signal);
        if (!active || request.signal.aborted) return;
        failures = 0;
        setState({ scope, data, error: "", loading: false, lastSuccess: Date.now(), retrying: false });
        delay = 20_000;
      } catch (error) {
        if (!active || (request.signal.aborted && !timedOut)) return;
        const retrying = timedOut || isTransient(error);
        if (retrying) {
          const base = [2_000, 4_000, 8_000, 16_000, 30_000][Math.min(failures++, 4)];
          delay = base * (0.8 + Math.random() * 0.4);
        }
        setState((previous) => ({
          ...(previous.scope === scope ? previous : { ...initial, scope }),
          loading: false,
          error: timedOut ? "Request timed out. Please try again." : callbacks.current.mapError(error),
          retrying,
        }));
      } finally {
        clearTimeout(deadline);
        controller = null;
        if (active && !document.hidden) {
          if (refreshOnSettle) {
            refreshOnSettle = false;
            void run();
          } else if (delay !== null) timer = setTimeout(run, delay);
        }
      }
    };

    const onVisibility = () => {
      clearTimeout(timer);
      refreshOnSettle = false;
      if (document.hidden) controller?.abort();
      else if (controller) refreshOnSettle = true;
      else void run();
    };
    void run();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [scope]);

  // Reset during render so returning to a previous range cannot resurrect its old values,
  // even if the intervening range's request never completed (or the tab was hidden).
  if (state.scope !== scope) {
    setState({ ...initial, scope });
    return initial;
  }
  return state;
}
