"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageToggle } from "./LanguageToggle";
import { useLocale } from "./LocaleProvider";
import { getBackOfficeURL } from "@/lib/site-urls";

function homeHref(pathname: string, hash: string) {
  return pathname === "/" ? hash : `/${hash}`;
}

export function SiteHeader() {
  const pathname = usePathname();
  const { copy } = useLocale();

  const navItems = [
    { href: homeHref(pathname, "#home"), label: copy.common.nav.home },
    { href: homeHref(pathname, "#services"), label: copy.common.nav.services },
    { href: homeHref(pathname, "#coverage"), label: copy.common.nav.coverage },
    { href: homeHref(pathname, "#contact"), label: copy.common.nav.contact },
  ];
  const backOfficeURL = getBackOfficeURL();

  return (
    <header className="sticky top-0 z-50 border-b border-mist bg-white/95 backdrop-blur" role="banner">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="text-2xl font-black text-navy" aria-label="TrackFlow home">
          TrackFlow
        </Link>
        <div className="flex items-center gap-6">
          <nav aria-label="Main navigation">
            <ul className="hidden list-none items-center gap-6 md:flex">
              {navItems.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="text-sm font-semibold text-neutral-700 transition hover:text-coral"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <Link
            href={backOfficeURL}
            className="hidden rounded-full border border-navy px-4 py-2 text-sm font-bold text-navy transition hover:bg-navy hover:text-white md:inline-flex"
          >
            {copy.common.nav.login}
          </Link>
          <LanguageToggle />
        </div>
      </div>
    </header>
  );
}
