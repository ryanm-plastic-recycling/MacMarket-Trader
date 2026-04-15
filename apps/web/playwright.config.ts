import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  // Next.js dev server cannot handle concurrent page navigations — run tests serially.
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:9501",
    trace: "on-first-retry",
  },
  webServer: {
    command: "node ./scripts/clean-next-cache.mjs && npm run dev -- --port 9501",
    port: 9501,
    reuseExistingServer: !process.env.CI,
    env: {
      NEXT_PUBLIC_E2E_BYPASS_AUTH: "true",
    },
  },
});
