"use client";

import Link from "next/link";
import { PackageMinus, Truck, type LucideIcon } from "lucide-react";
import { usePathname } from "next/navigation";

type OperationsSection = {
  label: string;
  href: string;
  icon: LucideIcon;
};

const operationsSections: OperationsSection[] = [
  { label: "Fulfilment", href: "/backoffice/operations/fulfilment", icon: Truck },
  { label: "Stock loss", href: "/backoffice/operations/stock-loss", icon: PackageMinus },
];

export function OperationsPageHeader({ title, description }: { title: string; description: string }) {
  const pathname = usePathname();

  return (
    <header className="mb-6">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Operations</p>
      <h1 className="mt-2 text-3xl font-black text-navy-deep">{title}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-600">{description}</p>
      <nav
        className="mt-5 flex w-fit max-w-full flex-wrap gap-1 rounded-xl border border-mist bg-ivory/70 p-1 shadow-sm"
        aria-label="Operations metric sections"
      >
        {operationsSections.map((section) => {
          const active = pathname === section.href;
          return (
            <Link
              key={section.href}
              href={section.href}
              aria-current={active ? "page" : undefined}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-black transition ${
                active
                  ? "border-navy bg-navy text-white shadow-sm"
                  : "border-transparent bg-white/80 text-navy hover:border-mist hover:bg-white"
              }`}
            >
              <section.icon className={`h-4 w-4 shrink-0 ${active ? "text-white" : "text-sky"}`} aria-hidden="true" />
              {section.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
