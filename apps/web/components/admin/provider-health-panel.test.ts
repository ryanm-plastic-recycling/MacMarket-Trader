import { describe, expect, it } from "vitest";

import { OPTIONS_PROVIDER_READINESS_NOTE } from "@/components/admin/provider-health-panel";

describe("provider health readiness copy", () => {
  it("keeps options/index provider guidance readiness-only", () => {
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("SPX/NDX may require index data access");
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("SPY/QQQ can be practical ETF substitutes");
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("Options chain, IV, Greeks, and open interest depend on provider coverage");
    expect(OPTIONS_PROVIDER_READINESS_NOTE).toContain("does not enable execution");
    expect(OPTIONS_PROVIDER_READINESS_NOTE.toLowerCase()).not.toContain("stage real order");
    expect(OPTIONS_PROVIDER_READINESS_NOTE.toLowerCase()).not.toContain("routing");
  });
});
