import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#101214",
        "surface-1": "#16191C",
        "surface-2": "#1C2024",
        "surface-3": "#23282D",
        elevated: "#2A3036",
        "border-subtle": "#2D3339",
        "border-strong": "#3B434B",
        "text-primary": "#F2F4F5",
        "text-secondary": "#B0B7BE",
        "text-muted": "#78828C",
        primary: "#2355C5",
        success: "#3E8063",
        warning: "#A77A32",
        danger: "#B85454",
        info: "#5279B8",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SF Mono", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
      },
    },
  },
  plugins: [],
} satisfies Config;
