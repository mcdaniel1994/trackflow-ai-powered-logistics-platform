"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { LanguageToggle } from "./LanguageToggle";
import { useLocale } from "./LocaleProvider";
import { getBackOfficeURL } from "@/lib/site-urls";

function homeHref(pathname: string, hash: string) {
  return pathname === "/" ? hash : `/${hash}`;
}

export function SiteHeader() {
  const pathname = usePathname();
  const { copy } = useLocale();
  const [menuOpen, setMenuOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const navItems = [
    { href: homeHref(pathname, "#home"), label: copy.common.nav.home },
    { href: homeHref(pathname, "#services"), label: copy.common.nav.services },
    { href: homeHref(pathname, "#coverage"), label: copy.common.nav.coverage },
    { href: homeHref(pathname, "#contact"), label: copy.common.nav.contact },
  ];
  const backOfficeURL = getBackOfficeURL();

  // The mobile panel carries every destination, including the apply and login
  // links the desktop header renders separately.
  const mobileItems = [
    ...navItems,
    { href: "/application", label: copy.common.nav.apply },
    { href: backOfficeURL, label: copy.common.nav.login },
  ];

  // Close on Escape and return focus to the trigger.
  useEffect(() => {
    if (!menuOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  function closeMenu() {
    setMenuOpen(false);
    triggerRef.current?.focus();
  }

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
          <button
            ref={triggerRef}
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded-md text-navy transition hover:text-coral md:hidden"
            aria-expanded={menuOpen}
            aria-controls="mobile-site-menu"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? (
              <X className="h-6 w-6" aria-hidden="true" />
            ) : (
              <Menu className="h-6 w-6" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {menuOpen ? (
        <>
          <button
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            className="fixed inset-0 top-16 z-40 cursor-default bg-navy-deep/20 md:hidden"
            onClick={closeMenu}
          />
          <nav
            id="mobile-site-menu"
            aria-label="Mobile navigation"
            className="absolute inset-x-0 top-16 z-50 border-b border-mist bg-white/95 backdrop-blur md:hidden"
          >
            <ul className="mx-auto max-w-7xl list-none px-4 py-2 sm:px-6 lg:px-8">
              {mobileItems.map((item) => (
                <li key={item.href} className="border-b border-mist last:border-b-0">
                  <Link
                    href={item.href}
                    className="flex min-h-11 items-center text-sm font-semibold text-neutral-700 transition hover:text-coral"
                    onClick={() => setMenuOpen(false)}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </>
      ) : null}
    </header>
  );
}
