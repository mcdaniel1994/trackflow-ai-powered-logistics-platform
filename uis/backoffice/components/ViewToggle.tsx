"use client";

import { Briefcase, Cpu } from "lucide-react";
import { type BackofficeView, useBackofficeView } from "@/lib/backoffice/view-context";

const OPTIONS: { value: BackofficeView; label: string; icon: typeof Briefcase }[] = [
  { value: "business", label: "Business", icon: Briefcase },
  { value: "technical", label: "Technical & Agent OS", icon: Cpu },
];

export function ViewToggle() {
  const { view, setView } = useBackofficeView();

  return (
    <div
      role="tablist"
      aria-label="Overview mode"
      className="inline-flex items-center gap-1 rounded-xl border border-mist bg-ivory p-1 dark:border-ink-600 dark:bg-ink-700"
    >
      {OPTIONS.map((option) => {
        const active = view === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => setView(option.value)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition sm:text-sm ${
              active
                ? "bg-white text-navy shadow-sm dark:bg-ink-900 dark:text-neutral-100"
                : "text-neutral-500 hover:text-navy dark:text-neutral-400 dark:hover:text-neutral-200"
            }`}
          >
            <option.icon className="h-4 w-4" aria-hidden="true" />
            <span className="whitespace-nowrap">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
