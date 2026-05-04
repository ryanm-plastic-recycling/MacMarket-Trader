import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  buildCloudflareAccessHeaders,
  mutationAllowed,
  pathIsUnderEvidence,
  redactedCloudflareAccessHeaders,
  resolveDeployedSmokeConfig,
  resolveSmokeEvidenceDir,
} from "./deployed-smoke-utils";

describe("deployed smoke auth helpers", () => {
  it("builds Cloudflare Access service-token headers without redacting runtime values", () => {
    const headers = buildCloudflareAccessHeaders({
      CF_ACCESS_CLIENT_ID: "client-id.access",
      CF_ACCESS_CLIENT_SECRET: "super-secret-value",
    });

    expect(headers).toEqual({
      "CF-Access-Client-Id": "client-id.access",
      "CF-Access-Client-Secret": "super-secret-value",
    });
  });

  it("redacts Cloudflare Access service-token values for summaries", () => {
    const headers = redactedCloudflareAccessHeaders({
      CF_ACCESS_CLIENT_ID: "client-id.access",
      CF_ACCESS_CLIENT_SECRET: "super-secret-value",
    });

    expect(headers["CF-Access-Client-Id"]).toBe("clie...cess");
    expect(headers["CF-Access-Client-Secret"]).toBe("supe...alue");
    expect(JSON.stringify(headers)).not.toContain("super-secret-value");
  });

  it("skips cleanly when smoke auth is missing", () => {
    const config = resolveDeployedSmokeConfig(
      { SMOKE_BASE_URL: "https://macmarket.io/" },
      { cwd: "C:/repo/apps/web", now: new Date("2026-05-04T12:00:00Z") },
    );

    expect(config.baseUrl).toBe("https://macmarket.io");
    expect(config.shouldSkip).toBe(true);
    expect(config.skipReason).toContain("Missing smoke auth");
    expect(config.authSummary.cloudflare_service_token).toBe("missing");
    expect(config.authSummary.storage_state).toBe("missing");
  });

  it("uses storage state as an authenticated smoke path", () => {
    const config = resolveDeployedSmokeConfig(
      { SMOKE_AUTH_STORAGE_STATE: "C:/safe/state.json" },
      { cwd: "C:/repo/apps/web", now: new Date("2026-05-04T12:00:00Z") },
    );

    expect(config.shouldSkip).toBe(false);
    expect(config.storageStatePath).toBe("C:/safe/state.json");
    expect(config.authSummary.storage_state).toBe("configured");
  });

  it("defaults mutation support to false unless explicitly enabled", () => {
    expect(mutationAllowed({})).toBe(false);
    expect(mutationAllowed({ SMOKE_ALLOW_MUTATION: "false" })).toBe(false);
    expect(mutationAllowed({ SMOKE_ALLOW_MUTATION: "true" })).toBe(true);
  });

  it("places evidence under the repo .tmp/evidence folder by default", () => {
    const evidence = resolveSmokeEvidenceDir(
      {},
      { cwd: "C:/repo/apps/web", now: new Date("2026-05-04T12:00:00Z") },
    );

    expect(evidence).toBe(path.join("C:/repo", ".tmp", "evidence", "deployed-ui-smoke-20260504T120000Z"));
    expect(pathIsUnderEvidence(evidence, "C:/repo/apps/web")).toBe(true);
  });
});
