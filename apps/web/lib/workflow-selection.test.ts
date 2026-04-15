import { describe, expect, it } from "vitest";

import { pickOrderSelection, pickReplayRunSelection } from "@/lib/workflow-selection";

describe("pickReplayRunSelection", () => {
  const runs = [
    { id: 9, symbol: "MSFT", source_recommendation_id: "rec-other" },
    { id: 10, symbol: "AAPL", source_recommendation_id: "rec-123" },
  ];

  it("returns null in guided mode when nothing matches", () => {
    const selected = pickReplayRunSelection({
      guided: true,
      requestedRecommendationId: "rec-missing",
      requestedSymbol: "AAPL",
      runs,
    });
    expect(selected).toBeNull();
  });

  it("prioritizes run query param in guided mode", () => {
    const selected = pickReplayRunSelection({
      guided: true,
      requestedRunId: "10",
      requestedRecommendationId: "rec-other",
      runs,
    });
    expect(selected).toBe(10);
  });
});

describe("pickOrderSelection", () => {
  const orders = [
    { order_id: "ord-1", replay_run_id: 51, recommendation_id: "rec-other" },
    { order_id: "ord-2", replay_run_id: 52, recommendation_id: "rec-123" },
  ];

  it("returns null in guided mode when nothing matches", () => {
    const selected = pickOrderSelection({
      guided: true,
      requestedReplayRunId: "999",
      requestedRecommendationId: "rec-missing",
      orders,
    });
    expect(selected).toBeNull();
  });

  it("prioritizes order query param in guided mode", () => {
    const selected = pickOrderSelection({
      guided: true,
      requestedOrderId: "ord-2",
      requestedReplayRunId: "51",
      orders,
    });
    expect(selected).toBe("ord-2");
  });
});
