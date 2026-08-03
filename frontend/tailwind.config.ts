import type { Config } from "tailwindcss";

/**
 * Colours are driven entirely by CSS custom properties declared in
 * `styles/globals.css`, so light and dark themes swap by flipping
 * `html[data-theme]` without any class-level duplication here.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Bricolage Grotesque Variable", "IBM Plex Sans", "sans-serif"],
        mono: ["JetBrains Mono Variable", "ui-monospace", "monospace"],
      },
      colors: {
        brand: {
          50: "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
          950: "rgb(var(--brand-950) / <alpha-value>)",
          DEFAULT: "rgb(var(--brand-500) / <alpha-value>)",
        },
        ink: "rgb(var(--ink-rgb) / <alpha-value>)",
        muted: "rgb(var(--ink-muted-rgb) / <alpha-value>)",
        subtle: "rgb(var(--ink-subtle-rgb) / <alpha-value>)",
        breach: "rgb(var(--breach-rgb) / <alpha-value>)",
        signal: "rgb(var(--signal-rgb) / <alpha-value>)",
        caution: "rgb(var(--caution-rgb) / <alpha-value>)",
        violet: "rgb(var(--violet-rgb) / <alpha-value>)",

        // Legacy aliases retained so existing markup renders on the new palette.
        slate: "rgb(var(--slate-rgb) / <alpha-value>)",
        tide: "rgb(var(--tide-rgb) / <alpha-value>)",
        ember: "rgb(var(--ember-rgb) / <alpha-value>)",
        moss: "rgb(var(--moss-rgb) / <alpha-value>)",
        mist: "rgb(var(--mist-rgb) / <alpha-value>)",
        sand: "rgb(var(--sand-rgb) / <alpha-value>)",
      },
      backgroundColor: {
        surface: "var(--surface)",
        "surface-muted": "var(--surface-muted)",
        "surface-sunken": "var(--surface-sunken)",
      },
      borderColor: {
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        card: "var(--shadow-sm)",
        elevated: "var(--shadow-md)",
        floating: "var(--shadow-lg)",
        brand: "var(--shadow-brand)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
      maxWidth: {
        shell: "1600px",
      },
    },
  },
  plugins: [],
};

export default config;
