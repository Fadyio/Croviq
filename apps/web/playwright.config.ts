import { defineConfig, devices } from "@playwright/test";

const loadBalancerIp = process.env.LOAD_BALANCER_IP || "8.233.204.233";

export default defineConfig({
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          args: [`--host-resolver-rules=MAP app.croviq.app ${loadBalancerIp}`],
        },
      },
    },
  ],
});
