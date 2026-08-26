import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0B0D0F",
        "surface-1": "#111418",
        "surface-2": "#171B20",
        "surface-3": "#1F242B",
        elevated: "#272E37",
        "border-subtle": "#22272F",
        "border-strong": "#323A45",
        "text-primary": "#F3F5F7",
        "text-secondary": "#9DA7B3",
        "text-muted": "#646E7B",
        primary: "#2563EB",
        "primary-hover": "#1D4ED8",
        success: "#10B981",
        warning: "#F59E0B",
        danger: "#EF4444",
        info: "#3B82F6",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SF Mono", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
    },
  },
  plugins: [],
} satisfies Config;
