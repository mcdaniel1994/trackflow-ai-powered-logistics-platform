"use client";

import { LeadForm } from "./LeadForm";
import { useLocale } from "@/components/layout/LocaleProvider";

export function ApplicationPage() {
  const { copy } = useLocale();

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
      <header className="mb-10">
        <h1 className="text-3xl font-black text-navy-deep sm:text-4xl">
          {copy.application.title}
        </h1>
        <p className="mt-3 text-lg leading-8 text-neutral-600">{copy.application.subtitle}</p>
      </header>
      <LeadForm />
    </div>
  );
}
