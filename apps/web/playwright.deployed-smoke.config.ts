import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "deployed-smoke.spec.ts",
  timeout: 120_000,
  workers: 1,
  use: {
    baseURL: process.env.SMOKE_BASE_URL || "https://macmarket.io",
    trace: "retain-on-failure",
  },
});
