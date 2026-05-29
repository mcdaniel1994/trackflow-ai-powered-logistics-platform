import { en } from "./site.en";
import { es } from "./site.es";
import type { Locale, Translation } from "./types";

export const translations: Record<Locale, Translation> = {
  en,
  es,
};

export const locales: Locale[] = ["en", "es"];
