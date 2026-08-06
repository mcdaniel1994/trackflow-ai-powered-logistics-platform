"use client";

import Link from "next/link";
import { Activity, ArrowRight, Bot, Boxes, Database, ScrollText } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type TechnicalCard = {
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  cta: string;
  badge?: string;
  disabled?: boolean;
};

const CARDS: TechnicalCard[] = [
  {
    title: "Technical Telemetry",
    description: "Fulfilment, receiving, stock-loss and security signals emitted by the platform.",
    href: "/backoffice/telemetry/fulfilment",
    icon: Activity,
    cta: "Open telemetry",
  },
  {
    title: "Inventory Management",
    description: "Products, orders and the immutable stock ledger behind the live operations feed.",
    href: "/backoffice/inventory/products",
    icon: Boxes,
    cta: "Open inventory",
  },
  {
    title: "Knowledge Vector Store",
    description: "The Qdrant collection powering Ask AI — chunked policy documents and embeddings.",
    href: "/agent-os",
    icon: Database,
    cta: "Powering Ask AI",
    disabled: true,
  },
  {
    title: "Agent OS",
    description: "Token usage, tools & connections, and per-agent context editors.",
    href: "/agent-os",
    icon: Bot,
    cta: "Open Agent OS",
  },
];

export function TechnicalOverview() {
  return (
    <section aria-label="Technical and Agent OS overview" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <ScrollText className="h-5 w-5 text-sky" aria-hidden="true" />
        <h2 className="text-lg font-black text-navy-deep dark:text-neutral-100">Technical &amp; Agent OS</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {CARDS.map((card) => (
          <TechnicalPanel key={card.title} card={card} />
        ))}
      </div>
    </section>
  );
}

function TechnicalPanel({ card }: { card: TechnicalCard }) {
  const body = (
    <div className="flex h-full flex-col gap-3 rounded-2xl border border-mist bg-white p-5 shadow-soft transition dark:border-ink-600 dark:bg-ink-800">
      <div className="flex items-center justify-between">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ivory text-navy dark:bg-ink-700 dark:text-neutral-100">
          <card.icon className="h-5 w-5" aria-hidden="true" />
        </span>
        {card.badge ? (
          <span className="rounded-full bg-teal/20 px-2 py-0.5 text-[0.6rem] font-black uppercase text-teal">
            {card.badge}
          </span>
        ) : null}
      </div>
      <div>
        <h3 className="text-base font-black text-navy-deep dark:text-neutral-100">{card.title}</h3>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-300">{card.description}</p>
      </div>
      <span
        className={`mt-auto inline-flex items-center gap-1 text-sm font-bold ${
          card.disabled ? "text-neutral-400 dark:text-neutral-500" : "text-sky"
        }`}
      >
        {card.cta}
        {!card.disabled ? <ArrowRight className="h-4 w-4" aria-hidden="true" /> : null}
      </span>
    </div>
  );

  if (card.disabled) {
    return <div aria-disabled="true">{body}</div>;
  }
  return (
    <Link href={card.href} className="block h-full">
      {body}
    </Link>
  );
}
