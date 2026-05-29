// Tailwind config. This app owns its own Tailwind build — `packages/tailwind-config/`
// is a separate CLI pipeline that only feeds the static marketing site and is NOT
// consumed here (per the spec). Next.js handles JIT compilation automatically.

import type { Config } from "tailwindcss";

const config: Config = {
  // `content` tells Tailwind which files to scan for class names so it knows
  // which utility classes to actually emit. Anything not referenced in these
  // globs gets purged from the production CSS.
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    // `extend` adds to Tailwind's defaults instead of replacing them — we still
    // get bg-white, text-red-700, etc., plus the TrackFlow tokens below.
    //
    // These hex values come straight from the marketing site's --jc-* (Junecoast)
    // palette so the two surfaces visually match. See spec § Visual Language.
    extend: {
      colors: {
        navy: {
          deep: "#2b486e",
          DEFAULT: "#2b4d74",
        },
        sky: "#4b7aa6",
        teal: "#6ebab8",
        coral: "#ed7e4d",
        ivory: "#f0eee6",
        mist: "#e9eef3",
        neutral: {
          50: "#f7fafc",
          100: "#e9eef3",
          200: "#d8e1ea",
          300: "#b9c8d8",
          500: "#6f87a5",
          600: "#507092",
          700: "#3a6088",
          900: "#2b486e",
        },
      },
    },
  },
  plugins: [],
};

export default config;
