"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { Activity, PanelLeftClose, PanelLeftOpen, Warehouse } from "lucide-react";
import { BackofficeNavigation } from "./BackofficeNavigation";

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  function toggleSidebar() {
    setSidebarCollapsed((current) => !current);
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-20 border-b border-mist/90 bg-white/95 backdrop-blur">
        <div className="flex h-16 w-full max-w-[100vw] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white shadow-sm">
              <Warehouse className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">
                TrackFlow
              </p>
              <p className="truncate text-lg font-black text-navy-deep">Backoffice</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 rounded-lg border border-mist bg-ivory px-3 py-2 text-sm font-bold text-navy sm:flex">
            <Activity className="h-4 w-4 text-teal" aria-hidden="true" />
            Internal operations
          </div>
        </div>
      </header>
      <div
        className={`grid w-full max-w-[100vw] grid-cols-1 transition-[grid-template-columns] duration-200 ${
          sidebarCollapsed ? "lg:grid-cols-[88px_minmax(0,1fr)]" : "lg:grid-cols-[260px_minmax(0,1fr)]"
        }`}
      >
        <aside
          className={`min-w-0 w-full max-w-[100vw] border-b border-mist/90 bg-white px-4 py-4 transition-[padding] duration-200 lg:sticky lg:top-16 lg:min-h-[calc(100vh-4rem)] lg:self-start lg:border-b-0 lg:border-r ${
            sidebarCollapsed ? "lg:px-4" : "lg:px-6"
          }`}
        >
          <button
            type="button"
            onClick={toggleSidebar}
            className={`mb-3 hidden h-10 w-full items-center rounded-lg border border-mist bg-white px-3 text-sm font-bold text-navy transition hover:bg-ivory lg:flex ${
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
        <main className="min-w-0 w-full max-w-[100vw] px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
