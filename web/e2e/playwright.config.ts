import { defineConfig, devices } from "@playwright/test";

// scripts/e2e.sh boots the single conbench binary with `conbench serve`
// (embedded SPA + API) and passes the live base URL; this config does not start
// a webServer itself.
const baseURL = process.env.CONBENCH_E2E_BASE_URL ?? "http://localhost:8099";

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
