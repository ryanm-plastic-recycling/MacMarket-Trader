import { describe, expect, it, vi } from "vitest";

const { fetchWorkflowApiMock } = vi.hoisted(() => ({
  fetchWorkflowApiMock: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  fetchWorkflowApi: fetchWorkflowApiMock,
}));

import {
  buildOptionsReplayPreviewRequest,
  buildOptionsPaperOpenRequest,
  canRenderOptionsResearchChart,
  describeOptionsCommissionEstimate,
  estimateOptionsCommissionForEvents,
  estimateOptionsCommissionPerEvent,
  fetchOptionsPaperClose,
  fetchOptionsPaperOpen,
  fetchOptionsReplayPreview,
  formatOptionsLegLabel,
  formatOptionsReplayToken,
  getExpectedRangeReasonText,
  getOptionsChainUnavailableMessage,
  getOptionsResearchDataQualityWarnings,
  getOptionsLegDisplayLines,
  getOptionsPaperOpenAvailability,
  getOptionsReplayPreviewAvailability,
  getOptionsReplayPreviewBreakevens,
  getOptionsReplayPreviewPayoffRows,
  formatResearchCell,
  formatResearchCurrency,
  formatResearchTimestamp,
  formatResearchValue,
  getOptionsPremiumLabel,
  getOptionsPremiumValue,
  getPromotedQueueKeys,
  getRankingProvenance,
  isFallbackWorkflow,
  isOptionsResearchMode,
  isReadOnlyResearchMode,
  parseRecommendationSearchParams,
  shouldShowRecommendationExecutionCtas,
} from "@/lib/recommendations";

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

describe("research preview helpers", () => {
  it("detects options and read-only research modes explicitly", () => {
    expect(isOptionsResearchMode("options")).toBe(true);
    expect(isOptionsResearchMode("equities")).toBe(false);
    expect(isReadOnlyResearchMode("options")).toBe(true);
    expect(isReadOnlyResearchMode("crypto")).toBe(true);
    expect(isReadOnlyResearchMode("equities")).toBe(false);
    expect(shouldShowRecommendationExecutionCtas("options")).toBe(false);
    expect(shouldShowRecommendationExecutionCtas("crypto")).toBe(false);
    expect(shouldShowRecommendationExecutionCtas("equities")).toBe(true);
  });

  it("formats missing research values safely", () => {
    expect(formatResearchValue(null)).toBe("Unavailable");
    expect(formatResearchValue(Number.NaN)).toBe("Unavailable");
    expect(formatResearchValue("")).toBe("Unavailable");
    expect(formatResearchValue(0)).toBe("0");
    expect(formatResearchCell(undefined)).toBe("—");
    expect(formatResearchCurrency(undefined)).toBe("Unavailable");
    expect(formatResearchCurrency(0)).toBe("$0.00");
  });

  it("formats option-leg labels with explicit action, right, strike, and label", () => {
    expect(
      formatOptionsLegLabel({ action: "sell", right: "call", strike: 205, label: "short call" }),
    ).toBe("sell CALL 205 — short call");
  });

  it("renders partial or missing leg detail safely", () => {
    expect(formatOptionsLegLabel({ label: "protective wing" })).toBe("protective wing");
    expect(getOptionsLegDisplayLines({ legs: [] })).toEqual(["Leg detail Unavailable."]);
  });

  it("returns the correct premium label and value for credit and debit structures", () => {
    expect(getOptionsPremiumLabel({ net_credit: 1.25 })).toBe("Net credit");
    expect(getOptionsPremiumValue({ net_credit: 1.25 })).toBe(1.25);
    expect(getOptionsPremiumLabel({ net_debit: 2.4 })).toBe("Net debit");
    expect(getOptionsPremiumValue({ net_debit: 2.4 })).toBe(2.4);
    expect(getOptionsPremiumLabel(null)).toBe("Net premium");
    expect(getOptionsPremiumValue(null)).toBeNull();
  });

  it("surfaces blocked and omitted expected-range reasons safely", () => {
    expect(getExpectedRangeReasonText({ status: "blocked", reason: "missing_iv_snapshot" })).toBe("missing_iv_snapshot");
    expect(getExpectedRangeReasonText({ status: "omitted", reason: "" })).toBe("Unavailable");
    expect(getExpectedRangeReasonText({ status: "computed", method: "iv_1sigma" })).toBeNull();
  });

  it("returns muted safe copy for missing chain preview states", () => {
    expect(getOptionsChainUnavailableMessage({ reason: "plan_not_configured" })).toBe("plan_not_configured");
    expect(getOptionsChainUnavailableMessage(null)).toBe("Chain preview unavailable on current provider plan or payload.");
  });

  it("formats as-of timestamps deterministically and renders unavailable safely", () => {
    expect(formatResearchTimestamp("2026-04-29T13:01:00Z")).toBe("2026-04-29 13:01 UTC");
    expect(formatResearchTimestamp("")).toBe("As-of unavailable");
  });

  it("builds data-quality warnings from existing source, chain, and expected-range payload gaps", () => {
    const warnings = getOptionsResearchDataQualityWarnings({
      symbol: "SPX",
      market_mode: "options",
      workflow_source: "",
      strategy: "Iron Condor",
      option_structure: {
        type: "iron_condor",
        expiration: "",
        dte: null,
        legs: [{ action: "buy", right: "put", strike: 90, label: "lower long put" }],
        net_credit: 2.5,
        iv_snapshot: null,
        theta_context: null,
        vega_context: null,
      },
      expected_range: {
        status: "blocked",
        method: null,
        reference_price_type: null,
        absolute_move: null,
        lower_bound: null,
        upper_bound: null,
        horizon_value: null,
        horizon_unit: null,
        snapshot_timestamp: null,
        provenance_notes: null,
        reason: "missing_iv_snapshot",
      },
      options_chain_preview: null,
    });

    expect(warnings).toContain("Underlying source unavailable.");
    expect(warnings).toContain("Expiration unavailable in the current research payload.");
    expect(warnings).toContain("DTE unavailable in the current research payload.");
    expect(warnings).toContain("IV snapshot unavailable in the current provider plan or payload.");
    expect(warnings).toContain("Greeks context unavailable in the current provider plan or payload.");
    expect(warnings).toContain("Open interest unavailable on the current Recommendations payload.");
    expect(warnings).toContain("Expected Range blocked: Missing IV Snapshot.");
    expect(warnings).toContain("Chain preview unavailable on current provider plan or payload.");
    expect(warnings).toContain("SPX/NDX may require index data; SPY/QQQ can be practical ETF substitutes.");
  });

  it("builds a replay preview request from a supported vertical debit research structure", () => {
    const request = buildOptionsReplayPreviewRequest({
      symbol: "AAPL",
      market_mode: "options",
      workflow_source: "polygon",
      strategy: "Bull Call Debit Spread",
      option_structure: {
        type: "bull_call_debit_spread",
        expiration: "2026-05-16",
        net_debit: 2.4,
        legs: [
          { action: "buy", right: "call", strike: 205, label: "long call" },
          { action: "sell", right: "call", strike: 215, label: "short call" },
        ],
      },
    });

    expect(request).toEqual({
      structure_type: "vertical_debit_spread",
      legs: [
        { action: "buy", right: "call", strike: 205, premium: 2.4, quantity: 1, multiplier: 100, label: "long call" },
        { action: "sell", right: "call", strike: 215, premium: 0, quantity: 1, multiplier: 100, label: "short call" },
      ],
      underlying_symbol: "AAPL",
      expiration: "2026-05-16",
      notes: ["Premium assumptions derived from the read-only research contract for expiration payoff preview."],
      source: "polygon",
      workflow_source: "polygon",
    });
  });

  it("builds an iron condor replay preview request from structure-level credit assumptions", () => {
    const request = buildOptionsReplayPreviewRequest({
      symbol: "SPY",
      market_mode: "options",
      workflow_source: "polygon",
      strategy: "Iron Condor",
      option_structure: {
        type: "iron_condor",
        expiration: "2026-05-16",
        net_credit: 2.5,
        legs: [
          { action: "buy", right: "put", strike: 90, label: "lower long put" },
          { action: "sell", right: "put", strike: 95, label: "short put" },
          { action: "sell", right: "call", strike: 105, label: "short call" },
          { action: "buy", right: "call", strike: 110, label: "higher long call" },
        ],
      },
    });

    expect(request?.structure_type).toBe("iron_condor");
    expect(request?.legs.map((leg) => leg.premium)).toEqual([0, 1.25, 1.25, 0]);
  });

  it("builds a paper option open request from a supported research structure", () => {
    const request = buildOptionsPaperOpenRequest({
      symbol: "AAPL",
      market_mode: "options",
      workflow_source: "polygon",
      strategy: "Bull Call Debit Spread",
      option_structure: {
        type: "bull_call_debit_spread",
        expiration: "2026-05-16",
        net_debit: 2.4,
        max_profit: 7.6,
        max_loss: 2.4,
        breakeven_low: 207.4,
        legs: [
          { action: "buy", right: "call", strike: 205, label: "long call" },
          { action: "sell", right: "call", strike: 215, label: "short call" },
        ],
      },
    });

    expect(request).toEqual({
      market_mode: "options",
      structure_type: "vertical_debit_spread",
      underlying_symbol: "AAPL",
      expiration: "2026-05-16",
      legs: [
        {
          action: "buy",
          right: "call",
          strike: 205,
          expiration: "2026-05-16",
          premium: 2.4,
          quantity: 1,
          multiplier: 100,
          label: "long call",
        },
        {
          action: "sell",
          right: "call",
          strike: 215,
          expiration: "2026-05-16",
          premium: 0,
          quantity: 1,
          multiplier: 100,
          label: "short call",
        },
      ],
      net_debit: 2.4,
      net_credit: null,
      max_profit: 7.6,
      max_loss: 2.4,
      breakevens: [207.4],
      notes: "Derived from the read-only options research contract for persisted paper-only lifecycle preview.",
    });
  });

  it("surfaces a disabled reason when the research structure is unsupported or incomplete", () => {
    expect(
      getOptionsReplayPreviewAvailability({
        symbol: "AAPL",
        market_mode: "options",
        workflow_source: "polygon",
        strategy: "Covered Call",
        option_structure: {
          type: "covered_call",
          legs: [{ action: "sell", right: "call", strike: 200 }],
        },
      }),
    ).toEqual({
      request: null,
      reason: "Replay payoff preview is currently supported only for long calls/puts, vertical debit spreads, and iron condors.",
    });

    expect(
      getOptionsReplayPreviewAvailability({
        symbol: "AAPL",
        market_mode: "options",
        workflow_source: "polygon",
        strategy: "Bull Call Debit Spread",
        option_structure: {
          type: "bull_call_debit_spread",
          legs: [{ action: "buy", right: "call", strike: 205 }],
        },
      }),
    ).toEqual({
      request: null,
      reason: "Replay payoff preview requires complete legs plus usable debit/credit or premium assumptions from the current research contract.",
    });

    expect(
      getOptionsPaperOpenAvailability({
        symbol: "AAPL",
        market_mode: "options",
        workflow_source: "polygon",
        strategy: "Bull Call Debit Spread",
        option_structure: {
          type: "bull_call_debit_spread",
          legs: [
            { action: "buy", right: "call", strike: 205, premium: 2.4 },
            { action: "sell", right: "call", strike: 215, premium: 0 },
          ],
        },
      }),
    ).toEqual({
      request: null,
      reason: "Paper option open requires a visible expiration for every leg.",
    });
  });

  it("formats replay tokens and filters preview rows safely", () => {
    expect(formatOptionsReplayToken("naked_short_option_not_supported")).toBe("Naked Short Option Not Supported");
    expect(getOptionsReplayPreviewBreakevens({
      execution_enabled: false,
      persistence_enabled: false,
      market_mode: "options",
      preview_type: "expiration_payoff",
      status: "ready",
      is_defined_risk: true,
      breakevens: [102.5, Number.NaN, 110],
      payoff_points: [
        { underlying_price: 100, total_payoff: -50 },
        { underlying_price: Number.NaN, total_payoff: 20 },
        { underlying_price: 110, total_payoff: Number.POSITIVE_INFINITY },
      ],
    })).toEqual([102.5, 110]);
    expect(getOptionsReplayPreviewPayoffRows({
      execution_enabled: false,
      persistence_enabled: false,
      market_mode: "options",
      preview_type: "expiration_payoff",
      status: "ready",
      is_defined_risk: true,
      payoff_points: [
        { underlying_price: 100, total_payoff: -50 },
        { underlying_price: Number.NaN, total_payoff: 20 },
        { underlying_price: 110, total_payoff: Number.POSITIVE_INFINITY },
      ],
    })).toEqual([{ underlying_price: 100, total_payoff: -50 }]);
  });

  it("posts replay preview requests through the same-origin helper", async () => {
    fetchWorkflowApiMock.mockResolvedValue({
      ok: true,
      status: 200,
      data: { status: "ready" },
      items: [],
      error: null,
      raw: { status: "ready" },
    });

    await fetchOptionsReplayPreview({
      structure_type: "vertical_debit_spread",
      legs: [{ action: "buy", right: "call", strike: 205, premium: 2.4 }],
    });

    expect(fetchWorkflowApiMock).toHaveBeenCalledWith("/api/user/options/replay-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        structure_type: "vertical_debit_spread",
        legs: [{ action: "buy", right: "call", strike: 205, premium: 2.4 }],
      }),
    });
  });

  it("posts paper option open requests through the same-origin helper", async () => {
    fetchWorkflowApiMock.mockResolvedValue({
      ok: true,
      status: 200,
      data: { position_id: 10 },
      items: [],
      error: null,
      raw: { position_id: 10 },
    });

    await fetchOptionsPaperOpen({
      market_mode: "options",
      structure_type: "vertical_debit_spread",
      underlying_symbol: "AAPL",
      expiration: "2026-05-16",
      legs: [
        { action: "buy", right: "call", strike: 205, expiration: "2026-05-16", premium: 2.4, quantity: 1, multiplier: 100 },
      ],
      breakevens: [],
    });

    expect(fetchWorkflowApiMock).toHaveBeenCalledWith("/api/user/options/paper-structures/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        market_mode: "options",
        structure_type: "vertical_debit_spread",
        underlying_symbol: "AAPL",
        expiration: "2026-05-16",
        legs: [
          { action: "buy", right: "call", strike: 205, expiration: "2026-05-16", premium: 2.4, quantity: 1, multiplier: 100 },
        ],
        breakevens: [],
      }),
    });
  });

  it("posts paper option close requests through the same-origin helper", async () => {
    fetchWorkflowApiMock.mockResolvedValue({
      ok: true,
      status: 200,
      data: { trade_id: 77 },
      items: [],
      error: null,
      raw: { trade_id: 77 },
    });

    await fetchOptionsPaperClose(42, {
      settlement_mode: "manual_close",
      legs: [{ position_leg_id: 101, exit_premium: 5.5 }],
    });

    expect(fetchWorkflowApiMock).toHaveBeenCalledWith("/api/user/options/paper-structures/42/close", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        settlement_mode: "manual_close",
        legs: [{ position_leg_id: 101, exit_premium: 5.5 }],
      }),
    });
  });

  it("estimates options commissions per contract per leg without multiplying by 100", () => {
    const legs = [
      { quantity: 1 },
      { quantity: 1 },
      { quantity: 1 },
      { quantity: 1 },
    ];

    expect(estimateOptionsCommissionPerEvent(legs, 0.65)).toBe(2.6);
    expect(estimateOptionsCommissionForEvents(legs, 0.65, 2)).toBe(5.2);
    expect(
      describeOptionsCommissionEstimate({
        commissionPerContract: 0.65,
        legs,
        eventCount: 2,
        eventLabel: "open/close",
      }),
    ).toBe("$0.65 x 1 contract x 4 legs x 2 open/close events = $5.20.");
  });

  it("only allows options research charts when source and symbol matching are safe", () => {
    expect(
      canRenderOptionsResearchChart({
        marketMode: "options",
        requestedSymbol: "AAPL",
        setupSymbol: "AAPL",
        workflowSource: "polygon",
      }),
    ).toBe(true);
    expect(
      canRenderOptionsResearchChart({
        marketMode: "options",
        requestedSymbol: "MSFT",
        setupSymbol: "AAPL",
        workflowSource: "polygon",
      }),
    ).toBe(false);
    expect(
      canRenderOptionsResearchChart({
        marketMode: "options",
        requestedSymbol: "AAPL",
        setupSymbol: "AAPL",
        workflowSource: "fallback (demo)",
      }),
    ).toBe(false);
  });
});
