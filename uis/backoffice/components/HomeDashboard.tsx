"use client";

import { AskKnowledgeBox } from "@/components/knowledge/AskKnowledgeBox";
import { OperationsOverview } from "@/components/OperationsOverview";
import { TechnicalOverview } from "@/components/TechnicalOverview";
import { useBackofficeView } from "@/lib/backoffice/view-context";

/**
 * The Back Office landing page. The query interface sits at the top; the overview below it
 * follows the top-center toggle — business operations, or the technical & Agent-OS surface.
 */
export function HomeDashboard() {
  const { view } = useBackofficeView();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      <div>
        <h1 className="mb-4 text-center text-2xl font-black text-navy-deep dark:text-neutral-100 sm:text-3xl">
          Where do you want to get started?
        </h1>
        <AskKnowledgeBox />
      </div>
      {view === "business" ? <OperationsOverview /> : <TechnicalOverview />}
    </div>
  );
}
