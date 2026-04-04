import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:9500",
    trace: "on-first-retry",
  },
  webServer: {
    command: "node ./scripts/clean-next-cache.mjs && npm run dev",
    port: 9500,
    reuseExistingServer: !process.env.CI,
    env: {
      NEXT_PUBLIC_E2E_BYPASS_AUTH: "true",
    },
  },
});
