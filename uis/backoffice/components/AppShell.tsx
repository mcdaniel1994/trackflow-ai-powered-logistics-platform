"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import Link from "next/link";
import { Menu, PanelLeftClose, PanelLeftOpen, Sparkles, Warehouse, X } from "lucide-react";
import { AccountMenu } from "@/components/account/AccountMenu";
import { BackofficeNavigation } from "@/components/BackofficeNavigation";
import { ViewToggle } from "@/components/ViewToggle";

function BrandMark() {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white shadow-sm dark:bg-sky">
        <Warehouse className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">TrackFlow</p>
        <p className="truncate text-lg font-black text-navy-deep dark:text-neutral-100">Backoffice</p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  function toggleSidebar() {
    setSidebarCollapsed((current) => !current);
  }

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-ink-900">
      <header className="sticky top-0 z-20 border-b border-mist/90 bg-white/95 backdrop-blur dark:border-ink-600 dark:bg-ink-900/95">
        <div className="flex h-16 w-full max-w-[100vw] items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileNavOpen((current) => !current)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-mist bg-white text-navy shadow-sm transition hover:bg-ivory dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100 lg:hidden"
              aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileNavOpen}
              aria-controls="mobile-backoffice-navigation"
            >
              {mobileNavOpen ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
            </button>
            <BrandMark />
          </div>

          <div className="hidden md:block">
            <ViewToggle />
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="hidden items-center gap-2 rounded-full border border-sky/60 bg-white px-4 py-2 text-sm font-black text-navy shadow-sm transition hover:border-sky hover:bg-ivory dark:border-sky/50 dark:bg-ink-800 dark:text-neutral-100 dark:hover:bg-ink-700 sm:inline-flex"
            >
              <Sparkles className="h-4 w-4 text-sky" aria-hidden="true" />
              Ask AI
            </Link>
            <AccountMenu />
          </div>
        </div>
        <div className="border-t border-mist/70 px-4 py-2 dark:border-ink-700 md:hidden">
          <ViewToggle />
        </div>
      </header>

      {mobileNavOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-navy-deep/20"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside
            id="mobile-backoffice-navigation"
            className="absolute left-0 top-0 h-full w-[min(22rem,calc(100vw-2rem))] overflow-y-auto border-r border-mist bg-white px-4 py-4 shadow-xl dark:border-ink-600 dark:bg-ink-900"
          >
            <div className="mb-4 flex items-center justify-between">
              <BrandMark />
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-mist bg-white text-navy transition hover:bg-ivory dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100"
                aria-label="Close navigation"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <BackofficeNavigation onNavigate={() => setMobileNavOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div
        className={`grid w-full max-w-[100vw] grid-cols-1 transition-[grid-template-columns] duration-200 ${
          sidebarCollapsed ? "lg:grid-cols-[76px_minmax(0,1fr)]" : "lg:grid-cols-[232px_minmax(0,1fr)]"
        }`}
      >
        <aside
          className={`hidden min-w-0 w-full max-w-[100vw] border-b border-mist/90 bg-white px-4 py-4 transition-[padding] duration-200 dark:border-ink-600 dark:bg-ink-900 lg:sticky lg:top-16 lg:block lg:min-h-[calc(100vh-4rem)] lg:self-start lg:border-b-0 lg:border-r ${
            sidebarCollapsed ? "lg:px-3" : "lg:px-4"
          }`}
        >
          <button
            type="button"
            onClick={toggleSidebar}
            className={`mb-3 hidden h-10 w-full items-center rounded-lg border border-mist bg-white px-3 text-sm font-bold text-navy transition hover:bg-ivory dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100 lg:flex ${
              sidebarCollapsed ? "justify-center" : "justify-between"
            }`}
            aria-label={sidebarCollapsed ? "Expand sidebar navigation" : "Collapse sidebar navigation"}
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
            ) : (
              <>
                <span>Collapse</span>
                <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
              </>
            )}
          </button>
          <BackofficeNavigation collapsed={sidebarCollapsed} />
        </aside>
        <main className="min-w-0 w-full max-w-[100vw] overflow-hidden px-4 py-8 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
