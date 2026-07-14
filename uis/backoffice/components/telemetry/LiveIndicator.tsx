"use client";

import { useEffect, useState } from "react";

function relativeLabel(lastUpdated: number | null, now: number): string {
  if (lastUpdated === null) return "connecting…";
  const seconds = Math.max(0, Math.round((now - lastUpdated) / 1000));
  if (seconds < 5) return "updated just now";
  if (seconds < 60) return `updated ${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `updated ${minutes}m ago`;
}

/** A calm "live" badge that reflects auto-refresh freshness without flashing the page. */
export function LiveIndicator({ lastUpdated }: { lastUpdated: number | null }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-mist bg-white px-3 py-1.5 text-xs font-bold text-neutral-600"
      aria-live="polite"
    >
      <span className="relative flex h-2 w-2" aria-hidden="true">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-teal" />
      </span>
      <span className="uppercase tracking-wide text-teal">Live</span>
      <span className="text-neutral-500">· {relativeLabel(lastUpdated, now)}</span>
    </span>
  );
}
