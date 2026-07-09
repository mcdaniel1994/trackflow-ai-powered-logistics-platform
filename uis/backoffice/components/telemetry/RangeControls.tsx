"use client";

import { useState } from "react";
import type { DateRange } from "@/lib/telemetry/types";

export function RangeControls({ value, onApply }: { value: DateRange; onApply: (range: DateRange) => void }) {
  const [from, setFrom] = useState(value.from);
  const [to, setTo] = useState(value.to);

  return (
    <form
      className="mb-5 flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        onApply({ from, to });
      }}
    >
      <label className="flex flex-col gap-1 text-xs font-black uppercase tracking-wide text-neutral-600">
        From
        <input
          type="date"
          value={from}
          max={to}
          onChange={(event) => setFrom(event.target.value)}
          className="rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy-deep"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs font-black uppercase tracking-wide text-neutral-600">
        To
        <input
          type="date"
          value={to}
          min={from}
          onChange={(event) => setTo(event.target.value)}
          className="rounded-lg border border-mist bg-white px-3 py-2 text-sm font-bold text-navy-deep"
        />
      </label>
      <button
        type="submit"
        className="rounded-lg border border-navy bg-navy px-4 py-2 text-sm font-black text-white transition hover:bg-navy-deep"
      >
        Apply
      </button>
    </form>
  );
}
