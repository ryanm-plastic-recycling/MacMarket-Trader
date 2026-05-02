import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import { OPTIONS_PROVIDER_READINESS_NOTE } from "@/components/admin/provider-health-panel";

const source = readFileSync(new URL("./provider-health-panel.tsx", import.meta.url), "utf8");

describe("provider health readiness copy", () => {
  it("keeps options/index provider guidance readiness-only", () => {
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("SPX/NDX may require index data access");
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("SPY/QQQ can be practical ETF substitutes");
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("Options chain, IV, Greeks, and open interest depend on provider coverage");
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("does not enable execution");
    expect(OPTIONS_PROVIDER_READINESS_NOTE.toLowerCase()).not.toContain("stage real order");
    expect(OPTIONS_PROVIDER_READINESS_NOTE.toLowerCase()).not.toContain("routing");
  });

  it("shows LLM provider health without exposing secret values", () => {
    expect(source).toContain("LLM provider");
    expect(source).toContain("LLM enabled");
    expect(source).toContain("key present");
    expect(source).toContain("fallback_reason");
    expect(source).toContain("last_error");
    expect(source).toContain("last_openai_error");
    expect(source).toContain("OpenAI status");
    expect(source).toContain("OpenAI request id");
    expect(source).toContain("config_state");
    expect(source).toContain("probe_state");
    expect(source).toContain("Probe not run");
    expect(source).toContain("Probe OK");
    expect(source).toContain("Probe failed");
    expect(source).toContain("probe_llm=true");
    expect(source).not.toContain("live probe:");
    expect(source).not.toContain("live probe: configured");
    expect(source).not.toContain("OPENAI_API_KEY");
    expect(source).not.toContain("sk-");
  });
});
