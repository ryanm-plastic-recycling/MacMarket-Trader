import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

import {
  DEPLOYED_SMOKE_PAGES,
  DeployedSmokeSummary,
  detectAuthGate,
  pageTextMatches,
  resolveDeployedSmokeConfig,
  SmokePageResult,
  summaryMarkdown,
} from "../deployed-smoke-utils";

const FORBIDDEN_LIVE_TRADING_COPY = [
  "live trading enabled",
  "broker routing enabled",
  "automatic exits enabled",
  "automatic rolls enabled",
  "automatic adjustments enabled",
];

async function writeSummary(summary: DeployedSmokeSummary): Promise<void> {
  await fs.mkdir(summary.evidence_dir, { recursive: true });
  await fs.writeFile(path.join(summary.evidence_dir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`, "utf-8");
  await fs.writeFile(path.join(summary.evidence_dir, "summary.md"), summaryMarkdown(summary), "utf-8");
}

test.describe("deployed macmarket.io UI smoke", () => {
  test("non-mutating deployed operator pages render behind safe auth", async ({ browser }) => {
    const config = resolveDeployedSmokeConfig();
    const summary: DeployedSmokeSummary = {
      status: "skipped",
      generated_at: new Date().toISOString(),
      base_url: config.baseUrl,
      auth: config.authSummary,
      mutation_allowed: config.mutationAllowed,
      evidence_dir: config.evidenceDir,
      screenshots_dir: config.screenshotsDir,
      skip_reason: config.skipReason,
      pages: [],
      findings: [],
    };

    await fs.mkdir(config.screenshotsDir, { recursive: true });

    if (config.shouldSkip) {
      await writeSummary(summary);
      test.skip(true, config.skipReason);
      return;
    }

    const context = await browser.newContext({
      extraHTTPHeaders: config.cloudflareAccessHeaders,
      storageState: config.storageStatePath,
      viewport: { width: 1440, height: 1000 },
    });
    const page = await context.newPage();
    const consoleErrors: string[] = [];
    const failedRequests: Array<{ url: string; failure: string }> = [];

    page.on("console", (message) => {
      if (["error", "warning"].includes(message.type())) {
        consoleErrors.push(message.text());
      }
    });
    page.on("requestfailed", (request) => {
      failedRequests.push({ url: request.url(), failure: request.failure()?.errorText || "request_failed" });
    });

    for (const definition of DEPLOYED_SMOKE_PAGES) {
      const pageConsoleStart = consoleErrors.length;
      const pageRequestStart = failedRequests.length;
      const pageResult: SmokePageResult = {
        name: definition.name,
        path: definition.path,
        status: "failed",
        missingText: [],
        matchedText: [],
        consoleErrors: [],
        failedRequests: [],
        notes: [],
      };
      const screenshotPath = path.join(
        config.screenshotsDir,
        `${definition.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}.png`,
      );

      try {
        const response = await page.goto(`${config.baseUrl}${definition.path}`, {
          waitUntil: "domcontentloaded",
          timeout: 30_000,
        });
        await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {
          pageResult.notes.push("networkidle_timeout_after_domcontentloaded");
        });
        pageResult.url = page.url();
        pageResult.screenshot = screenshotPath;
        await page.screenshot({ path: screenshotPath, fullPage: true });

        const bodyText = await page.locator("body").innerText({ timeout: 10_000 });
        const authGate = detectAuthGate(page.url(), bodyText);
        if (authGate) {
          pageResult.missingText.push(`authenticated app page; reached ${authGate}`);
          summary.findings.push({
            severity: "P1",
            title: `${definition.name} stopped at auth gate`,
            detail: authGate,
          });
        }

        if (!response || response.status() >= 500) {
          summary.findings.push({
            severity: "P1",
            title: `${definition.name} returned server error`,
            detail: response ? String(response.status()) : "no response",
          });
        }

        const textCheck = pageTextMatches(bodyText, definition);
        pageResult.missingText.push(...textCheck.missing);
        pageResult.matchedText.push(...textCheck.matched);

        const lowerBody = bodyText.toLowerCase();
        for (const forbidden of FORBIDDEN_LIVE_TRADING_COPY) {
          if (lowerBody.includes(forbidden)) {
            summary.findings.push({
              severity: "P1",
              title: `${definition.name} contains forbidden execution copy`,
              detail: forbidden,
            });
          }
        }

        pageResult.consoleErrors = consoleErrors.slice(pageConsoleStart);
        pageResult.failedRequests = failedRequests.slice(pageRequestStart);
        pageResult.status = pageResult.missingText.length || authGate ? "failed" : "passed";
      } catch (error) {
        pageResult.notes.push(error instanceof Error ? error.message : String(error));
        pageResult.consoleErrors = consoleErrors.slice(pageConsoleStart);
        pageResult.failedRequests = failedRequests.slice(pageRequestStart);
        summary.findings.push({
          severity: "P1",
          title: `${definition.name} navigation failed`,
          detail: pageResult.notes.join("; "),
        });
      }

      summary.pages.push(pageResult);
    }

    await context.close();

    const hardFailures = summary.findings.filter((finding) => finding.severity === "P0" || finding.severity === "P1");
    summary.status = hardFailures.length ? "failed" : "passed";
    delete summary.skip_reason;
    await writeSummary(summary);

    expect(summary.status).toBe("passed");
  });
});
