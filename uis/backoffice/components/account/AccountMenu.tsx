"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Info, KeyRound, LogOut, Moon, Sun, UserCog } from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { useTheme } from "@/lib/theme/context";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function AccountMenu() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex h-10 w-10 items-center justify-center rounded-full border border-mist bg-white text-sm font-black text-navy shadow-sm transition hover:border-sky dark:border-ink-600 dark:bg-ink-800 dark:text-neutral-100"
      >
        {initials(user.name)}
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 overflow-hidden rounded-xl border border-mist bg-white shadow-soft dark:border-ink-600 dark:bg-ink-800"
        >
          <div className="border-b border-mist px-4 py-3 dark:border-ink-600">
            <p className="truncate text-sm font-black text-navy-deep dark:text-neutral-100">{user.name}</p>
            <p className="truncate text-xs text-neutral-500 dark:text-neutral-400">{user.email}</p>
          </div>
          <div className="py-1">
            <Link
              href="/account/profile"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-neutral-600 transition hover:bg-ivory hover:text-navy dark:text-neutral-300 dark:hover:bg-ink-700 dark:hover:text-neutral-100"
            >
              <UserCog className="h-4 w-4" aria-hidden="true" />
              Account information
            </Link>
            <Link
              href="/account/change-password"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-neutral-600 transition hover:bg-ivory hover:text-navy dark:text-neutral-300 dark:hover:bg-ink-700 dark:hover:text-neutral-100"
            >
              <KeyRound className="h-4 w-4" aria-hidden="true" />
              Security
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={toggleTheme}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm font-bold text-neutral-600 transition hover:bg-ivory hover:text-navy dark:text-neutral-300 dark:hover:bg-ink-700 dark:hover:text-neutral-100"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
            <Link
              href="/about"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-neutral-600 transition hover:bg-ivory hover:text-navy dark:text-neutral-300 dark:hover:bg-ink-700 dark:hover:text-neutral-100"
            >
              <Info className="h-4 w-4" aria-hidden="true" />
              About &amp; disclaimers
            </Link>
          </div>
          <div className="border-t border-mist py-1 dark:border-ink-600">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                void logout();
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm font-bold text-coral transition hover:bg-coral/10"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Log out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
