"use client";

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";

/** The top-center overview toggle: business-facing vs technical/Agent-OS surfaces. */
export type BackofficeView = "business" | "technical";

export const VIEW_STORAGE_KEY = "trackflow-view";
const VIEW_CHANGE_EVENT = "trackflow-view-change";

type ViewContextValue = {
  view: BackofficeView;
  setView: (view: BackofficeView) => void;
};

const ViewContext = createContext<ViewContextValue | null>(null);

function subscribe(callback: () => void) {
  window.addEventListener(VIEW_CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(VIEW_CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function getSnapshot(): BackofficeView {
  try {
    const stored = window.localStorage.getItem(VIEW_STORAGE_KEY);
    if (stored === "business" || stored === "technical") return stored;
  } catch {
    // Ignore storage errors; fall through to the default.
  }
  return "business";
}

export function BackofficeViewProvider({ children }: { children: React.ReactNode }) {
  const view = useSyncExternalStore(subscribe, getSnapshot, () => "business" as BackofficeView);

  const setView = useCallback((next: BackofficeView) => {
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, next);
    } catch {
      // Non-fatal; the change event still notifies subscribers within this tab.
    }
    window.dispatchEvent(new Event(VIEW_CHANGE_EVENT));
  }, []);

  const value = useMemo(() => ({ view, setView }), [view, setView]);

  return <ViewContext.Provider value={value}>{children}</ViewContext.Provider>;
}

export function useBackofficeView() {
  const context = useContext(ViewContext);
  if (!context) {
    throw new Error("useBackofficeView must be used within BackofficeViewProvider.");
  }
  return context;
}
