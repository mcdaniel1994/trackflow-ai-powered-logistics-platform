"use client";

import { useEffect, useState } from "react";
import type { PollingResource } from "@/lib/hooks/useResourcePolling";

function useNow() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export function ResourceLiveIndicator({ resources }: { resources: PollingResource[] }) {
  const now = useNow();
  const live = resources.every((resource) => resource.lastSuccess !== null && !resource.error && now - resource.lastSuccess < 60_000);
  const anyData = resources.some((resource) => resource.lastSuccess !== null);
  const retrying = resources.some((resource) => resource.retrying);
  const label = live ? "Live" : anyData ? "Partial data" : resources.some((resource) => resource.error) ? "Unavailable" : "Connecting…";
  return (
    <span role="status" className={`inline-flex items-center gap-2 rounded-full border border-mist bg-white px-3 py-1.5 text-xs font-bold ${live ? "text-teal" : "text-neutral-600"}`}>
      <span className={`h-2 w-2 rounded-full ${live ? "bg-teal" : "bg-neutral-400"}`} aria-hidden="true" />
      {label}{!live && retrying ? " · retrying" : ""}
    </span>
  );
}

export function ResourceNotice({ resource, label }: { resource: PollingResource; label: string }) {
  const now = useNow();
  const stale = resource.lastSuccess !== null && (!!resource.error || now - resource.lastSuccess >= 60_000);
  return (
    <div className="mt-2 space-y-1 text-sm">
      {resource.loading ? <p className="text-neutral-600">Loading {label.toLowerCase()}…</p> : null}
      {resource.error ? <p role="alert" className="text-rose-800">{label}: {resource.error} · {resource.retrying ? "Retrying automatically." : "Refresh the page to try again."}</p> : null}
      {stale ? <p className="text-amber-800">Stale — last successful update <time dateTime={new Date(resource.lastSuccess!).toISOString()}>{new Date(resource.lastSuccess!).toLocaleString()}</time>.</p> : null}
    </div>
  );
}
