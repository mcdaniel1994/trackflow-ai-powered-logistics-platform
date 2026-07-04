"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "./LocaleProvider";
import { getBackOfficeURL } from "@/lib/site-urls";

function mobileHref(pathname: string, hash: string) {
  return pathname === "/" ? hash : `/${hash}`;
}

export function MobileNav() {
  const pathname = usePathname();
  const { copy } = useLocale();
  const backOfficeURL = getBackOfficeURL();

  const navItems = [
    { href: mobileHref(pathname, "#home"), label: copy.common.nav.home },
    { href: mobileHref(pathname, "#services"), label: copy.common.nav.services },
    { href: mobileHref(pathname, "#coverage"), label: copy.common.nav.coverage },
    { href: mobileHref(pathname, "#contact"), label: copy.common.nav.contact },
    { href: "/application", label: copy.common.nav.apply },
    { href: backOfficeURL, label: copy.common.nav.login },
  ];

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 grid grid-cols-6 border-t border-mist bg-white md:hidden"
      aria-label="Mobile navigation"
    >
      {navItems.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className="flex min-h-11 items-center justify-center px-1 py-2 text-center text-xs font-bold text-neutral-600 transition hover:bg-ivory hover:text-navy"
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
