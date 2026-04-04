import { describe, expect, it } from "vitest";

import { getRankingProvenance, isFallbackWorkflow, parseRecommendationSearchParams } from "@/lib/recommendations";

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
