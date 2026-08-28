import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ command, mode }) => {
  const envDir = typeof import.meta.dirname !== "undefined" ? import.meta.dirname : process.cwd();
  const env = { ...loadEnv(mode, process.cwd(), ""), ...loadEnv(mode, envDir, "") };
  const apiTarget = process.env.API_PROXY_TARGET || env.API_PROXY_TARGET || "http://localhost:8080";
  if (command === "build") {
    const requiredEnvVars = [
      "VITE_FIREBASE_API_KEY",
      "VITE_FIREBASE_AUTH_DOMAIN",
      "VITE_FIREBASE_PROJECT_ID",
    ] as const;
    const isCi = process.env.CI === "true";
    const missing = requiredEnvVars.filter((key) => {
      const val = isCi ? process.env[key] : process.env[key] || env[key];
      return !val || val.trim() === "" || val.startsWith("your-");
    });
    if (missing.length > 0) {
      throw new Error(
        `[vite.config] Missing required Firebase frontend build configuration: ${missing.join(
          ", ",
        )}. Production web builds must supply all required Firebase browser configuration values.`,
      );
    }
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      host: true,
      watch: {
        ignored: [
          "**/e2e/**",
          "**/test-results/**",
          "**/playwright-report/**",
          "**/screenshots/**",
        ],
      },
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
