/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont"],
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace"],
      },
      colors: {
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-strong": "rgb(var(--surface-strong) / <alpha-value>)",
        panel: "rgb(var(--panel) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        hover: "rgb(var(--hover) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        success: "rgb(var(--success) / <alpha-value>)",
        error: "rgb(var(--error) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};

