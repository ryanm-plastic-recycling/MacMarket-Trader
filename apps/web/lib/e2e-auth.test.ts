import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const workflowPageSources = [
  "../app/(console)/analysis/page.tsx",
  "../app/(console)/recommendations/page.tsx",
  "../app/(console)/replay-runs/page.tsx",
  "../app/(console)/orders/page.tsx",
].map((relativePath) => ({
  relativePath,
  source: readFileSync(new URL(relativePath, import.meta.url), "utf8"),
}));

describe("local E2E auth bypass", () => {
  it("does not wait for Clerk JS before protected workflow pages fetch data", () => {
    for (const { relativePath, source } of workflowPageSources) {
      expect(source, relativePath).toContain("const e2eBypass = isE2EAuthBypassEnabled();");
      expect(source, relativePath).toContain("const authReady = e2eBypass || (isLoaded && isSignedIn);");
      expect(source, relativePath).not.toContain("const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());");
    }
  });
});
