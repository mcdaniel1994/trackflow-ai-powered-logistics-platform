import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
}) {
  return (
    <article className="rounded-lg border border-mist/90 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-sky/35 hover:shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <p className="min-w-0 text-xs font-black uppercase tracking-[0.16em] text-neutral-500">
          {label}
        </p>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-mist bg-ivory text-navy">
          {icon}
        </div>
      </div>
      <p className="mt-4 min-w-0 break-words text-2xl font-black leading-tight text-navy-deep tabular-nums">
        {value}
      </p>
      <p className="mt-2 text-sm leading-6 text-neutral-600">{detail}</p>
    </article>
  );
}
