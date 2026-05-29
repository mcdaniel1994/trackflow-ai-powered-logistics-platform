"use client";

import { useLocale } from "./LocaleProvider";

export function LanguageToggle() {
  const { copy, toggleLocale } = useLocale();

  return (
    <button
      type="button"
      aria-label={copy.common.language.aria}
      onClick={toggleLocale}
      className="rounded-md border border-teal/70 bg-white/90 px-3 py-1.5 text-sm font-bold text-navy transition hover:bg-ivory"
    >
      {copy.common.language.next}
    </button>
  );
}
