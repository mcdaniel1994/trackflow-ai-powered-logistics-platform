import { useSyncExternalStore } from "react";
import type { ReportWarehouse } from "@/lib/reporting/types";

// Data-mark palettes, validated with the data-visualization contrast checker against the reporting
// surface (light #fcfcfb, dark ink-800 #141d2b). Do NOT substitute untested colors, and never use the
// raw brand tokens (navy/teal/sky) as marks — they fail the chroma/lightness checks and are reserved
// for chrome, text, and borders. Both palettes carry a sub-3:1 warning on the warm/teal slots, which
// is why every chart keeps visible labels and the precise data table is retained.
export const SERIES_LIGHT = ["#3d7ab8", "#ed7e4d", "#3fae9f", "#9a6ec4"] as const;
export const SERIES_DARK = ["#5090cf", "#dd7038", "#22a08c", "#a87fd4"] as const;

// Hues are assigned in a fixed order by entity so a filter or top-N change never repaints a series.
export const WAREHOUSE_SLOT: Record<ReportWarehouse, number> = {
  los_angeles: 0,
  zaragoza: 1,
};

export const WAREHOUSE_LABEL: Record<ReportWarehouse, string> = {
  los_angeles: "Los Angeles",
  zaragoza: "Zaragoza",
};

export const WAREHOUSE_ORDER: ReportWarehouse[] = ["los_angeles", "zaragoza"];

export function seriesColor(slot: number, theme: "light" | "dark"): string {
  const palette = theme === "dark" ? SERIES_DARK : SERIES_LIGHT;
  return palette[slot % palette.length];
}

// Matches lib/theme/context.tsx's internal THEME_CHANGE_EVENT. Reading the DOM class directly (rather
// than via useTheme) lets charts render outside ThemeProvider and stay in sync with the toggle.
const THEME_CHANGE_EVENT = "trackflow-theme-change";

function subscribeTheme(callback: () => void) {
  window.addEventListener(THEME_CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

export function useChartTheme(): "light" | "dark" {
  return useSyncExternalStore(
    subscribeTheme,
    () => (document.documentElement.classList.contains("dark") ? "dark" : "light"),
    () => "light",
  );
}
