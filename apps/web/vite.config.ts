import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = process.env.API_PROXY_TARGET || env.API_PROXY_TARGET || "http://localhost:8080";

  if (command === "build") {
    const requiredEnvVars = [
      "VITE_FIREBASE_API_KEY",
      "VITE_FIREBASE_AUTH_DOMAIN",
      "VITE_FIREBASE_PROJECT_ID",
    ] as const;

    const missing = requiredEnvVars.filter((key) => {
      const val = process.env[key] || env[key];
      return !val || val.trim() === "";
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
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
