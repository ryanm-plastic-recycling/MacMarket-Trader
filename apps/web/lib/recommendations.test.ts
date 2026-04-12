import { describe, expect, it } from "vitest";

import { getPromotedQueueKeys, getRankingProvenance, isFallbackWorkflow, parseRecommendationSearchParams } from "@/lib/recommendations";

describe("parseRecommendationSearchParams", () => {
  it("parses symbol and symbols query params into unique uppercase values", () => {
    const params = new URLSearchParams("symbol=aapl&symbols=msft,NVDA,aapl");
    expect(parseRecommendationSearchParams(params)).toEqual({
      symbols: ["MSFT", "NVDA", "AAPL"],
      recommendationId: null,
    });
  });

  it("returns recommendation id when present", () => {
    const params = new URLSearchParams("recommendation=rec-123");
    expect(parseRecommendationSearchParams(params)).toEqual({
      symbols: [],
      recommendationId: "rec-123",
    });
  });
});

describe("getRankingProvenance", () => {
  it("reads workflow ranking provenance", () => {
    expect(getRankingProvenance({ workflow: { ranking_provenance: { rank: 1 } } })).toEqual({ rank: 1 });
  });

  it("returns null when absent", () => {
    expect(getRankingProvenance({})).toBeNull();
  });
});

describe("getPromotedQueueKeys", () => {
  it("returns an empty set when no rows have ranking provenance", () => {
    const rows = [
      { id: 1, created_at: "2026-04-11", symbol: "AAPL", recommendation_id: "rec-1", payload: {} },
      { id: 2, created_at: "2026-04-11", symbol: "MSFT", recommendation_id: "rec-2", payload: { workflow: {} } },
    ];
    expect(getPromotedQueueKeys(rows)).toEqual(new Set());
  });

  it("returns the correct key for a promoted recommendation", () => {
    const rows = [
      {
        id: 1,
        created_at: "2026-04-11",
        symbol: "NVDA",
        recommendation_id: "rec-1",
        payload: {
          workflow: {
            ranking_provenance: { rank: 2, symbol: "NVDA", strategy: "Event Continuation" },
          },
        },
      },
    ];
    expect(getPromotedQueueKeys(rows)).toEqual(new Set(["NVDA-Event Continuation-2"]));
  });

  it("handles multiple promoted rows and returns all keys", () => {
    const rows = [
      {
        id: 1,
        created_at: "2026-04-11",
        symbol: "AAPL",
        recommendation_id: "rec-1",
        payload: { workflow: { ranking_provenance: { rank: 1, symbol: "AAPL", strategy: "Event Continuation" } } },
      },
      {
        id: 2,
        created_at: "2026-04-11",
        symbol: "MSFT",
        recommendation_id: "rec-2",
        payload: { workflow: { ranking_provenance: { rank: 3, symbol: "MSFT", strategy: "Breakout / Prior-Day High" } } },
      },
    ];
    const keys = getPromotedQueueKeys(rows);
    expect(keys).toEqual(new Set(["AAPL-Event Continuation-1", "MSFT-Breakout / Prior-Day High-3"]));
  });

  it("skips rows where provenance is missing symbol, strategy, or rank", () => {
    const rows = [
      {
        id: 1,
        created_at: "2026-04-11",
        symbol: "AAPL",
        recommendation_id: "rec-1",
        // rank missing
        payload: { workflow: { ranking_provenance: { symbol: "AAPL", strategy: "Event Continuation" } } },
      },
      {
        id: 2,
        created_at: "2026-04-11",
        symbol: "MSFT",
        recommendation_id: "rec-2",
        // strategy missing
        payload: { workflow: { ranking_provenance: { rank: 1, symbol: "MSFT" } } },
      },
      {
        id: 3,
        created_at: "2026-04-11",
        symbol: "NVDA",
        recommendation_id: "rec-3",
        // symbol missing
        payload: { workflow: { ranking_provenance: { rank: 2, strategy: "Event Continuation" } } },
      },
    ];
    expect(getPromotedQueueKeys(rows)).toEqual(new Set());
  });

  it("deduplicates identical provenance keys across multiple rows", () => {
    const provenance = { rank: 1, symbol: "AAPL", strategy: "Event Continuation" };
    const rows = [
      { id: 1, created_at: "2026-04-11", symbol: "AAPL", recommendation_id: "rec-1", payload: { workflow: { ranking_provenance: provenance } } },
      { id: 2, created_at: "2026-04-11", symbol: "AAPL", recommendation_id: "rec-2", payload: { workflow: { ranking_provenance: provenance } } },
    ];
    const keys = getPromotedQueueKeys(rows);
    expect(keys.size).toBe(1);
    expect(keys.has("AAPL-Event Continuation-1")).toBe(true);
  });
});

describe("isFallbackWorkflow", () => {
  it("detects fallback from stored recommendation metadata", () => {
    expect(
      isFallbackWorkflow(null, {
        id: 1,
        created_at: "2026-04-04",
        symbol: "AAPL",
        recommendation_id: "rec-1",
        payload: {},
        fallback_mode: true,
      }),
    ).toBe(true);
  });

  it("detects fallback queue source", () => {
    expect(
      isFallbackWorkflow(
        {
          rank: 1,
          symbol: "AAPL",
          strategy: "Event Continuation",
          workflow_source: "fallback (demo)",
          timeframe: "1D",
          status: "watchlist",
          score: 0.5,
          expected_rr: 1.5,
          confidence: 0.6,
          reason_text: "x",
          thesis: "x",
        },
        null,
      ),
    ).toBe(true);
  });
});
