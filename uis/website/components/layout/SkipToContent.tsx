"use client";

import { useLocale } from "./LocaleProvider";

export function SkipToContent() {
  const { copy } = useLocale();

  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-navy focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-soft"
    >
      {copy.common.skipContent}
    </a>
  );
}
