import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("dashboard market risk card", () => {
  it("renders deterministic Market Risk Today context without execution claims", () => {
    expect(source).toContain("Market Risk Today");
    expect(source).toContain("risk_calendar");
    expect(source).toContain("recommended_action");
    expect(source).toContain("Active events");
    expect(source).toContain("Missing evidence");
    expect(source.toLowerCase()).not.toContain("broker routing");
    expect(source.toLowerCase()).not.toContain("live trading");
  });
});
