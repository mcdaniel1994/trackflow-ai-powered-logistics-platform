"use client";

import { AskKnowledgeBox } from "@/components/knowledge/AskKnowledgeBox";
import { OperationsOverview } from "@/components/OperationsOverview";

/**
 * The Back Office landing page: the query interface sits at the top, with the live Operations
 * Overview below it (the Engagement 6 landing decision). The top-center view toggle was removed;
 * the sidebar is the sole navigation.
 */
export function HomeDashboard() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      <div>
        <h1 className="mb-4 text-center text-2xl font-black text-navy-deep dark:text-neutral-100 sm:text-3xl">
          Where do you want to get started?
        </h1>
        <AskKnowledgeBox />
      </div>
      <OperationsOverview />
    </div>
  );
}
