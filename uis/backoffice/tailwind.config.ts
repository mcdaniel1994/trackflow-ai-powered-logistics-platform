import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./content/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
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
      boxShadow: {
        soft: "0 16px 40px rgba(43, 72, 110, 0.14)",
      },
    },
  },
  plugins: [],
};

export default config;
