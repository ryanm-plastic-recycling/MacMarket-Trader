import { describe, expect, it } from "vitest";

import { formatExpectedMoveSummary } from "./analysis-expected-range";
import { buildGuidedQuery, GUIDED_ENTRY_PATH, GUIDED_FLOW_LABEL, GUIDED_STEPS, parseGuidedFlowState } from "./guided-workflow";

describe("guided workflow entry", () => {
  it("exports canonical guided CTA and path", () => {
    expect(GUIDED_FLOW_LABEL).toBe("Start guided paper trade");
    expect(GUIDED_ENTRY_PATH).toBe("/analysis?guided=1");
    expect(GUIDED_STEPS).toEqual(["Analyze", "Recommendation", "Replay", "Paper Order"]);
  });

  it("parses and rebuilds guided continuity query state", () => {
    const params = new URLSearchParams("guided=1&symbol=AAPL&strategy=Event+Continuation&recommendation=rec-1&replay_run=12&order=ord-7");
    const state = parseGuidedFlowState(params);
    expect(state).toEqual({
      guided: true,
      symbol: "AAPL",
      strategy: "Event Continuation",
      recommendationId: "rec-1",
      replayRunId: "12",
      orderId: "ord-7",
    });
    const rebuilt = new URLSearchParams(buildGuidedQuery(state));
    expect(rebuilt.get("guided")).toBe("1");
    expect(rebuilt.get("symbol")).toBe("AAPL");
    expect(rebuilt.get("strategy")).toBe("Event Continuation");
    expect(rebuilt.get("recommendation")).toBe("rec-1");
    expect(rebuilt.get("replay_run")).toBe("12");
    expect(rebuilt.get("order")).toBe("ord-7");
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
    expect(summary).toContain("current preview method");
    expect(summary).toContain("196");
    expect(summary).toContain("204.4");
  });

  it("formats blocked reason text", () => {
    expect(formatExpectedMoveSummary({ status: "blocked", reason: "insufficient_iv_quality" })).toContain("insufficient_iv_quality");
  });
});
