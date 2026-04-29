import { describe, expect, it } from "vitest";

import {
  formatLineageBreadcrumb,
  shortOrderId,
  shortRecommendationId,
  shortReplayRunId,
} from "./lineage-format";
import type { GuidedFlowState } from "@/lib/guided-workflow";

describe("shortRecommendationId", () => {
  it("returns em-dash for null/undefined/empty", () => {
    expect(shortRecommendationId(null)).toBe("—");
    expect(shortRecommendationId(undefined)).toBe("—");
    expect(shortRecommendationId("")).toBe("—");
    expect(shortRecommendationId("   ")).toBe("—");
  });

  it("strips the rec_ prefix and keeps the last 6 hex characters", () => {
    expect(shortRecommendationId("rec_a65757eb8d23")).toBe("Rec #eb8d23");
  });

  it("returns the full id when the hex tail is shorter than 6 characters", () => {
    expect(shortRecommendationId("rec_abc")).toBe("Rec #abc");
  });

  it("works on ids without the rec_ prefix", () => {
    expect(shortRecommendationId("a65757eb8d23")).toBe("Rec #eb8d23");
  });
});

describe("shortReplayRunId", () => {
  it("returns 'Replay pending' for null/empty", () => {
    expect(shortReplayRunId(null)).toBe("Replay pending");
    expect(shortReplayRunId(undefined)).toBe("Replay pending");
    expect(shortReplayRunId("")).toBe("Replay pending");
  });

  it("prefixes numeric ids", () => {
    expect(shortReplayRunId(25)).toBe("Replay #25");
    expect(shortReplayRunId("12")).toBe("Replay #12");
  });
});

describe("shortOrderId", () => {
  it("returns 'Order pending' for null/empty", () => {
    expect(shortOrderId(null)).toBe("Order pending");
    expect(shortOrderId(undefined)).toBe("Order pending");
    expect(shortOrderId("")).toBe("Order pending");
  });

  it("strips ord_ prefix and keeps last 6 chars", () => {
    expect(shortOrderId("ord_b1c2d3e4f5g6")).toBe("Order #e4f5g6");
  });

  it("returns full id when shorter than 6 chars", () => {
    expect(shortOrderId("ord_abc")).toBe("Order #abc");
  });
});

describe("formatLineageBreadcrumb", () => {
  const baseState: GuidedFlowState = { guided: true, symbol: "AAPL", strategy: "Event Continuation" };

  it("renders the full chain with symbol + strategy + ID-shortened tokens", () => {
    expect(
      formatLineageBreadcrumb(baseState, {
        recommendationId: "rec_a65757eb8d23",
        replayRunId: 25,
        orderId: null,
      }),
    ).toBe("AAPL Event Continuation · Rec #eb8d23 → Replay #25 → Order pending");
  });

  it("falls back to em-dash tokens when state lacks fields", () => {
    expect(formatLineageBreadcrumb({ guided: true }, {})).toBe("— — · — → Replay pending → Order pending");
  });

  it("prefers the selected override values over state values", () => {
    const result = formatLineageBreadcrumb(
      { guided: true, symbol: "AAPL", strategy: "Pullback", recommendationId: "rec_old123abcdef" },
      { symbol: "MSFT", strategy: "Breakout", recommendationId: "rec_new987fedcba" },
    );
    expect(result).toBe("MSFT Breakout · Rec #fedcba → Replay pending → Order pending");
  });

  it("renders Order #shortid when an order id is present", () => {
    const result = formatLineageBreadcrumb(baseState, {
      recommendationId: "rec_a65757eb8d23",
      replayRunId: 25,
      orderId: "ord_b1c2d3e4f5g6",
    });
    expect(result).toBe("AAPL Event Continuation · Rec #eb8d23 → Replay #25 → Order #e4f5g6");
  });

  it("accepts null state", () => {
    expect(formatLineageBreadcrumb(null, { symbol: "TSLA", strategy: "Mean Reversion" })).toBe(
      "TSLA Mean Reversion · — → Replay pending → Order pending",
    );
  });

  it("prefers backend display_id when provided", () => {
    expect(
      formatLineageBreadcrumb(baseState, {
        recommendationId: "rec_a65757eb8d23",
        recommendationDisplayId: "AAPL-EVCONT-20260429-0830",
        replayRunId: 25,
      }),
    ).toBe("AAPL Event Continuation · AAPL-EVCONT-20260429-0830 → Replay #25 → Order pending");
  });

  it("falls back to auto-shortened rec id when display_id is empty", () => {
    expect(
      formatLineageBreadcrumb(baseState, {
        recommendationId: "rec_a65757eb8d23",
        recommendationDisplayId: null,
        replayRunId: 25,
      }),
    ).toBe("AAPL Event Continuation · Rec #eb8d23 → Replay #25 → Order pending");
  });
});
