import { describe, expect, it } from "vitest";

import { formatExpectedMoveSummary } from "./analysis-expected-range";
import { GUIDED_ENTRY_PATH, GUIDED_FLOW_LABEL, GUIDED_STEPS } from "./guided-workflow";

describe("guided workflow entry", () => {
  it("exports canonical guided CTA and path", () => {
    expect(GUIDED_FLOW_LABEL).toBe("Start guided paper trade");
    expect(GUIDED_ENTRY_PATH).toBe("/analysis?guided=1");
    expect(GUIDED_STEPS).toEqual(["Analyze", "Recommendation", "Replay", "Paper Order"]);
  });
});

describe("analysis expected move summary", () => {
  it("formats computed expected move card text", () => {
    const summary = formatExpectedMoveSummary({
      status: "computed",
      method: "iv_1sigma",
      absolute_move: 4.2,
      lower_bound: 196,
      upper_bound: 204.4,
      horizon_value: 30,
      horizon_unit: "calendar_days",
    });
    expect(summary).toContain("iv_1sigma");
    expect(summary).toContain("196");
    expect(summary).toContain("204.4");
  });

  it("formats blocked reason text", () => {
    expect(formatExpectedMoveSummary({ status: "blocked", reason: "insufficient_iv_quality" })).toContain("insufficient_iv_quality");
  });
});
