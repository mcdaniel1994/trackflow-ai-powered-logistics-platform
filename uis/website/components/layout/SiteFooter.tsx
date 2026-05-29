"use client";

import Link from "next/link";
import { useLocale } from "./LocaleProvider";

export function SiteFooter() {
  const { copy } = useLocale();

  return (
    <footer className="bg-navy-deep py-8 text-ivory" role="contentinfo">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6 lg:px-8">
        <div className="space-y-1 text-center sm:text-left">
          <p className="text-sm">{copy.common.footer.copyright}</p>
          <p className="text-xs text-mist">{copy.common.footer.updated}</p>
        </div>
        <div className="flex items-center gap-6">
          <Link href="/privacy" className="text-sm transition hover:text-white">
            {copy.common.footer.privacy}
          </Link>
          <a
            href="https://linkedin.com/company/trackflow"
            className="text-sm transition hover:text-white"
            aria-label="TrackFlow on LinkedIn"
            rel="noopener noreferrer"
            target="_blank"
          >
            {copy.common.footer.linkedin}
          </a>
        </div>
      </div>
    </footer>
  );
}
