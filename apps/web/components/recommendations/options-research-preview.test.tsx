import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "module";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/charts/workflow-chart", () => ({
  WorkflowChart: () => null,
}));

vi.mock("@/components/operator-ui", async () => {
  const ReactModule = await import("react");
  return {
    Card: ({ title, children }: { title?: string; children: ReactNode }) =>
      ReactModule.createElement(
        "section",
        {},
        title ? ReactModule.createElement("h3", {}, title) : null,
        children,
      ),
    EmptyState: ({ title, hint }: { title: string; hint: string }) =>
      ReactModule.createElement("div", {}, `${title} ${hint}`),
    ErrorState: ({ title, hint }: { title: string; hint: string }) =>
      ReactModule.createElement("div", {}, `${title} ${hint}`),
    StatusBadge: ({ children }: { children: ReactNode }) =>
      ReactModule.createElement("span", {}, children),
  };
});

import {
  OptionsPaperLifecyclePanel,
  OptionsReplayPreviewPanel,
  OptionsResearchPreview,
  OptionsStructureRiskSummary,
  OptionsWorkflowStepper,
} from "@/components/recommendations/options-research-preview";
import type {
  OptionsReplayPreviewAvailability,
  OptionsReplayPreviewResponse,
  OptionsResearchSetup,
} from "@/lib/recommendations";
import {
  getOptionsPaperOpenAvailability,
  getOptionsReplayPreviewAvailability,
} from "@/lib/recommendations";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("OptionsReplayPreviewPanel", () => {
  it("renders ready preview details and payoff table without execution CTAs", () => {
    const availability: OptionsReplayPreviewAvailability = {
      request: {
        structure_type: "vertical_debit_spread",
        legs: [
          { action: "buy", right: "call", strike: 100, premium: 4 },
          { action: "sell", right: "call", strike: 110, premium: 0 },
        ],
      },
      reason: null,
    };
    const preview: OptionsReplayPreviewResponse = {
      execution_enabled: false,
      persistence_enabled: false,
      market_mode: "options",
      preview_type: "expiration_payoff",
      status: "ready",
      structure_type: "vertical_debit_spread",
      is_defined_risk: true,
      net_debit: 4,
      max_profit: 600,
      max_loss: 400,
      breakevens: [104],
      payoff_points: [
        { underlying_price: 100, total_payoff: -400, leg_payoffs: [] },
        { underlying_price: 104, total_payoff: 0, leg_payoffs: [] },
        { underlying_price: 120, total_payoff: 600, leg_payoffs: [] },
      ],
      warnings: [],
      caveats: ["paper_only_preview"],
      blocked_reason: null,
      operator_disclaimer: "Options research only. Paper-only preview. Not execution support.",
    };

    const html = renderToStaticMarkup(
      <OptionsReplayPreviewPanel
        availability={availability}
        preview={preview}
        loading={false}
        error={null}
        onRunPreview={() => undefined}
      />,
    );

    expect(html).toContain("Replay payoff preview");
    expect(html).toContain("Read-only, non-persisted expiration payoff");
    expect(html).toContain("Vertical Debit Spread");
    expect(html).toContain("$600.00");
    expect(html).toContain("$400.00");
    expect(html).toContain("$104.00");
    expect(html).toContain("Expiration payoff table");
    expect(html).toContain("Preview payoff only");
    expect(html).toContain("Does not save a position");
    expect(html).toContain("$0.00");
    expect(html).not.toContain("Execution disabled");
    expect(html).not.toContain("Execution enabled:");
    expect(html).not.toContain("Promote selected queue candidate");
    expect(html).not.toContain("Go to Replay step");
    expect(html).not.toContain("Go to Paper Order step");
  });

  it("renders blocked reasons and disabled preview copy safely", () => {
    const availability: OptionsReplayPreviewAvailability = {
      request: null,
      reason: "Replay payoff preview requires visible option legs.",
    };
    const preview: OptionsReplayPreviewResponse = {
      execution_enabled: false,
      persistence_enabled: false,
      market_mode: "options",
      preview_type: "expiration_payoff",
      status: "blocked",
      structure_type: "long_call",
      is_defined_risk: false,
      net_debit: null,
      net_credit: null,
      max_profit: null,
      max_loss: null,
      breakevens: [],
      payoff_points: [],
      warnings: [],
      caveats: ["paper_only_preview"],
      blocked_reason: "naked_short_option_not_supported",
      operator_disclaimer: "Options research only. Paper-only preview. Not execution support.",
    };

    const html = renderToStaticMarkup(
      <OptionsReplayPreviewPanel
        availability={availability}
        preview={preview}
        loading={false}
        error={null}
        onRunPreview={() => undefined}
      />,
    );

    expect(html).toContain("Replay payoff preview requires visible option legs.");
    expect(html).toContain("Naked Short Option Not Supported");
    expect(html).toContain("Unavailable");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
  });
});

describe("OptionsWorkflowStepper", () => {
  const openResult = {
    order_id: 11,
    position_id: 12,
    market_mode: "options" as const,
    structure_type: "vertical_debit_spread",
    underlying_symbol: "AAPL",
    status: "open",
    order_status: "opened",
    position_status: "open",
    opening_net_debit: 2.4,
    opening_net_credit: null,
    commission_per_contract: 0.65,
    opening_commissions: 1.3,
    max_profit: 760,
    max_loss: 240,
    breakevens: [207.4],
    execution_enabled: false,
    persistence_enabled: true,
    paper_only: true,
    order_created_at: "2026-04-29T13:00:00Z",
    position_opened_at: "2026-04-29T13:00:00Z",
    legs: [],
  };

  const closeResult = {
    position_id: 12,
    trade_id: 22,
    market_mode: "options" as const,
    structure_type: "vertical_debit_spread",
    underlying_symbol: "AAPL",
    status: "closed",
    position_status: "closed",
    settlement_mode: "manual_close",
    commission_per_contract: 0.65,
    opening_commissions: 1.3,
    closing_commissions: 1.3,
    gross_pnl: 300,
    net_pnl: 297.4,
    total_commissions: 2.6,
    execution_enabled: false,
    persistence_enabled: true,
    paper_only: true,
    closed_at: "2026-04-29T15:00:00Z",
    legs: [],
  };

  it("renders guided workflow states across preview, paper-open, manual-close, and result phases", () => {
    const baseHtml = renderToStaticMarkup(
      <OptionsWorkflowStepper
        replayPreview={null}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );
    expect(baseHtml).toContain("Guided options workflow");
    expect(baseHtml).toContain("Current step: Step 1 — Review structure");

    const previewHtml = renderToStaticMarkup(
      <OptionsWorkflowStepper
        replayPreview={{
          execution_enabled: false,
          persistence_enabled: false,
          market_mode: "options",
          preview_type: "expiration_payoff",
          status: "ready",
          structure_type: "vertical_debit_spread",
          is_defined_risk: true,
          net_debit: 2.4,
          max_profit: 760,
          max_loss: 240,
          breakevens: [207.4],
          payoff_points: [],
          warnings: [],
          caveats: [],
          blocked_reason: null,
        }}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );
    expect(previewHtml).toContain("Current step: Step 2 — Preview payoff");

    const openHtml = renderToStaticMarkup(
      <OptionsWorkflowStepper
        replayPreview={null}
        paperOpenResult={openResult}
        paperCloseResult={null}
        closeDraftActive={false}
      />,
    );
    expect(openHtml).toContain("Current step: Step 3 — Save paper position");

    const closeDraftHtml = renderToStaticMarkup(
      <OptionsWorkflowStepper
        replayPreview={null}
        paperOpenResult={openResult}
        paperCloseResult={null}
        closeDraftActive
      />,
    );
    expect(closeDraftHtml).toContain("Current step: Step 4 — Manually close");

    const closedHtml = renderToStaticMarkup(
      <OptionsWorkflowStepper
        replayPreview={null}
        paperOpenResult={openResult}
        paperCloseResult={closeResult}
        closeDraftActive
      />,
    );
    expect(closedHtml).toContain("Current step: Step 5 — Review paper close result");
  });
});

describe("OptionsResearchPreview", () => {
  it("renders expected range as contextual research, not payoff math", () => {
    const html = renderToStaticMarkup(
      <OptionsResearchPreview
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-15",
            dte: 16,
            net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            breakeven_low: 92.5,
            breakeven_high: 107.5,
            legs: [
              {
                action: "buy",
                right: "put",
                strike: 90,
                label: "Long put wing",
                option_symbol: "O:SPY260515P00090000",
                target_strike: 90.25,
                selected_listed_strike: 90,
                strike_snap_distance: 0.25,
                strike_snap_allowed: 5,
                current_mark_premium: 1.24,
                mark_method: "quote_mid",
                premium_source: "quote_mid",
                implied_volatility: 0.22,
                open_interest: 1234,
                delta: -0.18,
                gamma: 0.02,
                theta: -0.04,
                vega: 0.11,
              },
              { action: "sell", right: "put", strike: 95, label: "Short put body" },
              { action: "sell", right: "call", strike: 105, label: "Short call body" },
              { action: "buy", right: "call", strike: 110, label: "Long call wing" },
            ],
          },
          expected_range: {
            status: "blocked",
            method: null,
            absolute_move: null,
            lower_bound: null,
            upper_bound: null,
            horizon_value: null,
            horizon_unit: null,
            reason: "missing_iv_snapshot",
          },
          options_chain_preview: null,
        }}
        loading={false}
        error={null}
        chartPayload={null}
        chartStorageKey="test-options-preview"
        chartSourceLabel="polygon"
        chartBlockedByFallback={false}
      />,
    );

    expect(html).toContain("Expected range is research context only. It does not change expiration payoff math or enable execution.");
    expect(html).toContain("Selected listed contract snapshots");
    expect(html).toContain("O:SPY260515P00090000");
    expect(html).toContain("quote_mid");
    expect(html).toContain("target");
    expect(html).toContain("selected");
    expect(html).toContain("snap 0.25 / allowed 5");
    expect(html).toContain("premium source quote_mid");
    expect(html).toContain("IV");
    expect(html).toContain("OI");
    expect(html).toContain("delta");
    expect(html).toContain("missing_iv_snapshot");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
  });

  it("renders paper lifecycle guardrails separately from replay preview", () => {
    const html = renderToStaticMarkup(
      <OptionsResearchPreview
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-15",
            dte: 16,
            net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            breakeven_low: 92.5,
            breakeven_high: 107.5,
            legs: [
              { action: "buy", right: "put", strike: 90, label: "Long put wing" },
              { action: "sell", right: "put", strike: 95, label: "Short put body" },
              { action: "sell", right: "call", strike: 105, label: "Short call body" },
              { action: "buy", right: "call", strike: 110, label: "Long call wing" },
            ],
          },
          expected_range: null,
          options_chain_preview: null,
        }}
        loading={false}
        error={null}
        chartPayload={null}
        chartStorageKey="test-options-preview"
        chartSourceLabel="polygon"
        chartBlockedByFallback={false}
      />,
    );

    expect(html).toContain("Replay payoff preview");
    expect(html).toContain("Paper option lifecycle");
    expect(html).toContain("Guided options workflow");
    expect(html).toContain("Current step: Step 1 — Review structure");
    expect(html).toContain("Structure risk");
    expect(html).toContain("Warnings");
    expect(html).toContain("Save as paper option position");
    expect(html).toContain("Creates persisted paper-only position/trade records");
    expect(html).toContain("No broker order is placed");
    expect(html).toContain("Not per share. Do not multiply by 100.");
    expect(html).toContain("Total options commission = commission per contract x contracts x legs x open/close events.");
    expect(html).toContain("Example: $0.65 commission, 1 iron condor, 4 legs, open + close = $0.65 x 1 x 4 x 2 = $5.20 total estimated commission.");
    expect(html).toContain("Preview payoff only — does not save a position.");
    expect(html).not.toContain("broker orders");
    expect(html).not.toContain("Go to Replay step");
    expect(html).not.toContain("Go to Paper Order step");
  });

  it("explains reference-only chain snapshots and incomplete chain sides safely", () => {
    const html = renderToStaticMarkup(
      <OptionsResearchPreview
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-15",
            dte: 16,
            net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            breakeven_low: 92.5,
            breakeven_high: 107.5,
            legs: [
              { action: "buy", right: "put", strike: 90, label: "Long put wing" },
              { action: "sell", right: "put", strike: 95, label: "Short put body" },
              { action: "sell", right: "call", strike: 105, label: "Short call body" },
              { action: "buy", right: "call", strike: 110, label: "Long call wing" },
            ],
          },
          expected_range: null,
          options_chain_preview: {
            underlying: "SPY",
            expiry: "2026-05-15",
            calls: [{ strike: 590, expiry: "2026-05-15", last_price: null, volume: null }],
            puts: null,
            data_as_of: "2026-04-29T13:01:00Z",
            source: "polygon_options_basic",
            reason: null,
          },
        }}
        loading={false}
        error={null}
        chartPayload={null}
        chartStorageKey="test-options-preview"
        chartSourceLabel="polygon"
        chartBlockedByFallback={false}
      />,
    );

    expect(html).toContain("Chain preview is showing available reference data. Last/volume may be unavailable from the current provider source or tier.");
    expect(html).toContain("Missing quote or volume fields are not used for payoff math. Liquidity quality cannot be fully assessed from this chain snapshot.");
    expect(html).toContain("Incomplete chain side: puts were not returned for this expiry/source. Defined-risk structures such as iron condors require both call and put context for a complete chain review.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
    expect(html).not.toContain("live trading");
    expect(html).not.toContain("broker execution");
  });

  it("shows blocked state and disables lifecycle actions for invalid listed-contract structures", () => {
    const setup: OptionsResearchSetup = {
      symbol: "QQQ",
      market_mode: "options",
      workflow_source: "polygon",
      strategy: "Iron Condor",
      option_structure: {
        type: "iron_condor",
        expiration: "2026-05-16",
        dte: 13,
        net_credit: 4.52,
        max_profit: null,
        max_loss: null,
        breakeven_low: null,
        breakeven_high: null,
        contract_resolution_status: "unresolved",
        contract_resolution_summary: "Cannot build iron condor: provider returned incomplete chain; puts missing.",
        structure_validation_status: "invalid",
        structure_validation_summary: "Cannot build iron condor: provider returned incomplete chain; puts missing.",
        paper_persistence_allowed: false,
        legs: [
          { action: "buy", right: "put", strike: 480, label: "lower long put" },
          { action: "sell", right: "put", strike: 480, label: "short put" },
          { action: "sell", right: "call", strike: 480, label: "short call" },
          { action: "buy", right: "call", strike: 480, label: "higher long call" },
        ],
      },
      expected_range: {
        status: "blocked",
        method: null,
        reference_price_type: "underlying_last",
        lower_bound: null,
        upper_bound: null,
        absolute_move: null,
        horizon_value: 13,
        horizon_unit: "calendar_days",
        reason: "Cannot build iron condor: provider returned incomplete chain; puts missing.",
      },
      options_chain_preview: {
        underlying: "QQQ",
        expiry: "2026-05-16",
        calls: [{ strike: 480, expiry: "2026-05-16", last_price: null, volume: null }],
        puts: null,
        source: "polygon_options_basic",
      },
    };

    expect(getOptionsReplayPreviewAvailability(setup).request).toBeNull();
    expect(getOptionsPaperOpenAvailability(setup).request).toBeNull();

    const lifecycleHtml = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={setup}
        loadCommissionOnMount={false}
      />,
    );
    const riskHtml = renderToStaticMarkup(
      <OptionsStructureRiskSummary
        setup={setup}
        replayPreview={null}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );

    expect(lifecycleHtml).toContain("Cannot build iron condor: provider returned incomplete chain; puts missing.");
    expect(lifecycleHtml).toContain("disabled");
    expect(lifecycleHtml).not.toContain("-$452.00");
    expect(riskHtml).toContain("Expected Range blocked");
    expect(riskHtml).toContain("Unavailable. Cannot build iron condor: provider returned incomplete chain; puts missing.");
    expect(riskHtml).not.toContain("Breakeven 1");
  });

  it("shows strike snap diagnostics and hides payoff markers when selected contracts are too far", () => {
    const setup: OptionsResearchSetup = {
      symbol: "AAPL",
      market_mode: "options",
      workflow_source: "polygon",
      strategy: "Iron Condor",
      option_structure: {
        type: "iron_condor",
        expiration: "2026-05-16",
        dte: 13,
        contract_resolution_status: "unresolved",
        contract_resolution_summary: "Unable to resolve listed contract near target strike. Target 292.75 selected 185.00, snap 107.75 exceeds allowed threshold 5.00.",
        structure_validation_status: "invalid",
        structure_validation_summary: "Unable to resolve listed contract near target strike. Target 292.75 selected 185.00, snap 107.75 exceeds allowed threshold 5.00.",
        paper_persistence_allowed: false,
        opening_price_source: "theoretical_estimate",
        fresh_provider_pricing_available: false,
        theoretical_net_credit: 1.88,
        max_profit: null,
        max_loss: null,
        legs: [
          { action: "buy", right: "put", strike: 175, label: "lower long put", option_symbol: "O:AAPL260516P00175000", target_strike: 260.53, selected_listed_strike: 175, strike_snap_distance: 85.53, strike_snap_allowed: 5 },
          { action: "sell", right: "put", strike: 180, label: "short put", option_symbol: "O:AAPL260516P00180000", target_strike: 267.53, selected_listed_strike: 180, strike_snap_distance: 87.53, strike_snap_allowed: 5 },
          { action: "sell", right: "call", strike: 185, label: "short call", option_symbol: "O:AAPL260516C00185000", target_strike: 292.75, selected_listed_strike: 185, strike_snap_distance: 107.75, strike_snap_allowed: 5, current_mark_premium: 100.71, mark_method: "quote_mid", premium_source: "quote_mid" },
          { action: "buy", right: "call", strike: 190, label: "higher long call", option_symbol: "O:AAPL260516C00190000", target_strike: 299.75, selected_listed_strike: 190, strike_snap_distance: 109.75, strike_snap_allowed: 5, current_mark_premium: 92.63, mark_method: "quote_mid", premium_source: "quote_mid" },
        ],
      },
      expected_range: {
        status: "blocked",
        method: null,
        reference_price_type: "underlying_last",
        lower_bound: null,
        upper_bound: null,
        absolute_move: null,
        horizon_value: 13,
        horizon_unit: "calendar_days",
        reason: "Unable to resolve listed contract near target strike. Target 292.75 selected 185.00, snap 107.75 exceeds allowed threshold 5.00.",
      },
      options_chain_preview: null,
    };

    expect(getOptionsReplayPreviewAvailability(setup).request).toBeNull();
    expect(getOptionsPaperOpenAvailability(setup).request).toBeNull();

    const html = renderToStaticMarkup(
      <OptionsResearchPreview
        setup={setup}
        loading={false}
        error={null}
        chartPayload={null}
        chartStorageKey="test-options-preview-snap-blocked"
        chartSourceLabel="polygon"
        chartBlockedByFallback={false}
      />,
    );

    expect(html).toContain("Target 292.75 selected 185.00, snap 107.75 exceeds allowed threshold 5.00");
    expect(html).toContain("snap 107.75 / allowed 5");
    expect(html).toContain("Opening price source");
    expect(html).toContain("theoretical_estimate");
    expect(html).toContain("Fresh quote_mid or last_trade marks are required before paper persistence.");
    expect(html).toContain("disabled");
    expect(html).not.toContain("Breakeven 1");
    expect(html).not.toContain("-$312.00");
  });

  it("renders Analysis Packet preview with macro, news, IV, OI, Greeks, and missing fields", () => {
    const html = renderToStaticMarkup(
      <OptionsResearchPreview
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-16",
            dte: 13,
            legs: [
              {
                action: "sell",
                right: "call",
                strike: 520,
                label: "short call",
                option_symbol: "O:SPY260516C00520000",
                current_mark_premium: 1.24,
                mark_method: "quote_mid",
                implied_volatility: 0.22,
                open_interest: 1234,
                delta: 0.18,
              },
            ],
          },
          expected_range: null,
          options_chain_preview: null,
          analysis_packet: {
            symbol: "SPY",
            market_mode: "options",
            timeframe: "1D",
            provider: "polygon",
            macro_context: {
              series: [{ series_id: "DGS10", label: "10Y Treasury yield", latest_value: 4.5, latest_date: "2026-05-01" }],
            },
            news_context: {
              headlines: [{ title: "SPY macro desk update", publisher: "Example Wire", published_utc: "2026-05-03T14:00:00Z" }],
            },
            options: {
              strategy_type: "iron_condor",
              expiration: "2026-05-16",
              days_to_expiration: 13,
              legs: [
                {
                  label: "short call",
                  action: "sell",
                  right: "call",
                  option_symbol: "O:SPY260516C00520000",
                  current_mark_premium: 1.24,
                  mark_method: "quote_mid",
                  implied_volatility: 0.22,
                  open_interest: 1234,
                  delta: 0.18,
                },
              ],
            },
            missing_data: ["options:option_snapshot_marks"],
          },
        }}
        loading={false}
        error={null}
        chartPayload={null}
        chartStorageKey="test-options-preview"
        chartSourceLabel="polygon"
        chartBlockedByFallback={false}
      />,
    );

    expect(html).toContain("Preview Analysis Packet");
    expect(html).toContain("Macro Context");
    expect(html).toContain("News Context");
    expect(html).toContain("10Y Treasury yield");
    expect(html).toContain("SPY macro desk update");
    expect(html).toContain("IV");
    expect(html).toContain("OI");
    expect(html).toContain("delta");
    expect(html).toContain("Missing from selected contract snapshot");
    expect(html).toContain("Missing data: options:option_snapshot_marks");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("NaN");
  });
});

describe("OptionsStructureRiskSummary", () => {
  it("renders compact structure risk details from research, replay preview, and paper lifecycle state", () => {
    const html = renderToStaticMarkup(
      <OptionsStructureRiskSummary
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-15",
            dte: 16,
            net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            breakeven_low: 92.5,
            breakeven_high: 107.5,
            legs: [
              { action: "buy", right: "put", strike: 90, multiplier: 100, label: "Long put wing" },
              { action: "sell", right: "put", strike: 95, multiplier: 100, label: "Short put body" },
              { action: "sell", right: "call", strike: 105, multiplier: 100, label: "Short call body" },
              { action: "buy", right: "call", strike: 110, multiplier: 100, label: "Long call wing" },
            ],
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
        }}
        replayPreview={{
          execution_enabled: false,
          persistence_enabled: false,
          market_mode: "options",
          preview_type: "expiration_payoff",
          status: "ready",
          structure_type: "iron_condor",
          is_defined_risk: true,
          net_credit: 2.6,
          max_profit: 260,
          max_loss: 240,
          breakevens: [93, 107],
          payoff_points: [],
          warnings: [],
          caveats: [],
          blocked_reason: null,
          operator_disclaimer: "Options research only. Paper-only preview. Not execution support.",
        }}
        paperOpenResult={{
          order_id: 31,
          position_id: 41,
          market_mode: "options",
          structure_type: "iron_condor",
          underlying_symbol: "SPY",
          status: "open",
          order_status: "opened",
          position_status: "open",
          opening_net_debit: null,
          opening_net_credit: 2.6,
          commission_per_contract: 0.65,
          opening_commissions: 2.6,
          max_profit: 260,
          max_loss: 240,
          breakevens: [93, 107],
          execution_enabled: false,
          persistence_enabled: true,
          paper_only: true,
          order_created_at: "2026-04-29T13:00:00Z",
          position_opened_at: "2026-04-29T13:00:00Z",
          legs: [
            {
              id: 401,
              position_id: 41,
              action: "buy",
              right: "put",
              strike: 90,
              expiration: "2026-05-15",
              quantity: 1,
              multiplier: 100,
              entry_premium: 0.3,
              status: "open",
              label: "Long put wing",
            },
            {
              id: 402,
              position_id: 41,
              action: "sell",
              right: "put",
              strike: 95,
              expiration: "2026-05-15",
              quantity: 1,
              multiplier: 100,
              entry_premium: 1.6,
              status: "open",
              label: "Short put body",
            },
            {
              id: 403,
              position_id: 41,
              action: "sell",
              right: "call",
              strike: 105,
              expiration: "2026-05-15",
              quantity: 1,
              multiplier: 100,
              entry_premium: 1.6,
              status: "open",
              label: "Short call body",
            },
            {
              id: 404,
              position_id: 41,
              action: "buy",
              right: "call",
              strike: 110,
              expiration: "2026-05-15",
              quantity: 1,
              multiplier: 100,
              entry_premium: 0.3,
              status: "open",
              label: "Long call wing",
            },
          ],
        }}
        paperCloseResult={{
          position_id: 41,
          trade_id: 77,
          market_mode: "options",
          structure_type: "iron_condor",
          underlying_symbol: "SPY",
          status: "closed",
          position_status: "closed",
          settlement_mode: "manual_close",
          commission_per_contract: 0.65,
          opening_commissions: 2.6,
          closing_commissions: 2.6,
          gross_pnl: 180,
          net_pnl: 174.8,
          total_commissions: 5.2,
          execution_enabled: false,
          persistence_enabled: true,
          paper_only: true,
          closed_at: "2026-04-29T15:00:00Z",
          legs: [],
        }}
      />,
    );

    expect(html).toContain("Research preview — read-only");
    expect(html).toContain("Replay payoff preview — non-persisted");
    expect(html).toContain("Paper lifecycle — persisted paper only");
    expect(html).toContain("Iron Condor");
    expect(html).toContain("$260.00");
    expect(html).toContain("$240.00");
    expect(html).toContain("$93.00 / $107.00");
    expect(html).toContain("Provider and data quality");
    expect(html).toContain("Chain preview unavailable on current provider plan or payload.");
    expect(html).toContain("Source unavailable / As-of unavailable means the current provider plan or payload did not supply that field on this options surface.");
    expect(html).toContain("Manually closed");
    expect(html).toContain("$180.00");
    expect(html).toContain("$174.80");
    expect(html).toContain("Help: Max profit");
    expect(html).toContain("Help: Max loss");
    expect(html).toContain("Help: Breakevens");
    expect(html).toContain("Help: Expected Range");
    expect(html).toContain("The largest modeled gain for the structure");
    expect(html).toContain("The largest modeled loss for the structure");
    expect(html).toContain("Underlying price where the structure&#x27;s modeled payoff");
    expect(html).toContain("Paper profit or loss before commissions are subtracted.");
    expect(html).toContain("Paper profit or loss after modeled commissions are subtracted.");
    expect(html).toContain("The paper options fee applied per contract, per leg, per open or close event.");
    expect(html).toContain("Expected Range is research context only. It does not modify expiration payoff math.");
    expect(html).toContain("Commission is per contract per leg, not multiplied by 100.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
    expect(html).not.toContain("Live trading");
    expect(html).not.toContain("Broker execution");
  });

  it("renders missing risk values safely when replay preview and paper lifecycle have not started", () => {
    const html = renderToStaticMarkup(
      <OptionsStructureRiskSummary
        setup={{
          symbol: "QQQ",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Long Call",
          option_structure: {
            type: "long_call",
            expiration: null,
            dte: null,
            legs: [{ action: "buy", right: "call", strike: null, multiplier: null, label: "Call leg" }],
            net_debit: null,
            max_profit: null,
            max_loss: null,
          },
          expected_range: null,
          options_chain_preview: null,
        }}
        replayPreview={null}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );

    expect(html).toContain("Unavailable");
    expect(html).toContain("Not run yet");
    expect(html).toContain("Not opened");
    expect(html).toContain("Expected range context unavailable for this setup.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });
});

describe("OptionsPaperLifecyclePanel", () => {
  const setup = {
    symbol: "AAPL",
    market_mode: "options",
    workflow_source: "polygon",
    strategy: "Bull Call Debit Spread",
    option_structure: {
      type: "bull_call_debit_spread",
      expiration: "2026-05-16",
      dte: 17,
      net_debit: 2.4,
      max_profit: 760,
      max_loss: 240,
      breakeven_low: 207.4,
      legs: [
        { action: "buy", right: "call", strike: 205, label: "Long call" },
        { action: "sell", right: "call", strike: 215, label: "Short call" },
      ],
    },
    expected_range: null,
    options_chain_preview: null,
  };

  it("renders a disabled message for unsupported or incomplete paper structures", () => {
    const html = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={{
          ...setup,
          option_structure: {
            type: "covered_call",
            legs: [{ action: "sell", right: "call", strike: 210, label: "Short call" }],
          },
        }}
        loadCommissionOnMount={false}
      />,
    );

    expect(html).toContain("Paper option open currently supports long calls/puts, vertical debit spreads, and iron condors only.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
  });

  it("renders manual close inputs with exit-premium explanations and long/short hints", () => {
    const html = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={setup}
        initialCommissionPerContract={0.65}
        initialOpenResult={{
          order_id: 11,
          position_id: 12,
          market_mode: "options",
          structure_type: "vertical_debit_spread",
          underlying_symbol: "AAPL",
          status: "open",
          order_status: "opened",
          position_status: "open",
          opening_net_debit: 2.4,
          opening_net_credit: null,
          commission_per_contract: 0.65,
          opening_commissions: 1.3,
          max_profit: 760,
          max_loss: 240,
          breakevens: [207.4],
          execution_enabled: false,
          persistence_enabled: true,
          paper_only: true,
          operator_disclaimer: "paper only",
          order_created_at: "2026-04-29T13:00:00Z",
          position_opened_at: "2026-04-29T13:00:00Z",
          legs: [
            {
              id: 101,
              position_id: 12,
              action: "buy",
              right: "call",
              strike: 205,
              expiration: "2026-05-16",
              quantity: 1,
              multiplier: 100,
              entry_premium: 4.2,
              exit_premium: null,
              status: "open",
              label: "Long call",
            },
            {
              id: 102,
              position_id: 12,
              action: "sell",
              right: "call",
              strike: 215,
              expiration: "2026-05-16",
              quantity: 1,
              multiplier: 100,
              entry_premium: 1.8,
              exit_premium: null,
              status: "open",
              label: "Short call",
            },
          ],
        }}
        loadCommissionOnMount={false}
      />,
    );

    expect(html).toContain("Save as paper option position");
    expect(html).toContain("This stays separate from the read-only replay payoff preview above and does not place a broker order.");
    expect(html).toContain("Exit premium");
    expect(html).toContain("Enter the option premium to simulate closing this leg.");
    expect(html).toContain("Example: 1.25 means $1.25 per contract.");
    expect(html).toContain("Long leg hint: higher exit premium generally helps this leg.");
    expect(html).toContain("Short leg hint: lower exit premium generally helps this leg.");
    expect(html).toContain("P&amp;L uses premium x 100. Commission is not multiplied by 100.");
  });

  it("renders listed contract resolution and unresolvable contract warnings", () => {
    const resolvedHtml = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-16",
            dte: 13,
            net_credit: 2.4,
            max_profit: 240,
            max_loss: 260,
            contract_resolution_status: "resolved",
            paper_persistence_allowed: true,
            legs: [
              { action: "buy", right: "put", strike: 660, premium: 0, option_symbol: "O:SPY260516P00660000", target_strike: 661.77 },
              { action: "sell", right: "put", strike: 665, premium: 1.2, option_symbol: "O:SPY260516P00665000", target_strike: 664.2 },
              { action: "sell", right: "call", strike: 700, premium: 1.2, option_symbol: "O:SPY260516C00700000", target_strike: 699.8 },
              { action: "buy", right: "call", strike: 705, premium: 0, option_symbol: "O:SPY260516C00705000", target_strike: 704.9 },
            ],
          },
        }}
        loadCommissionOnMount={false}
      />,
    );
    expect(resolvedHtml).toContain("Selected listed contracts from provider chain.");
    expect(resolvedHtml).toContain("O:SPY260516P00660000");

    const unresolvedHtml = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "2026-05-16",
            dte: 13,
            net_credit: 2.4,
            max_profit: 240,
            max_loss: 260,
            contract_resolution_status: "unresolved",
            paper_persistence_allowed: false,
            contract_resolution_summary: "Unable to resolve listed contracts; paper position cannot be marked.",
            legs: [{ action: "buy", right: "put", strike: 661.77, premium: 0, label: "lower long put" }],
          },
        }}
        loadCommissionOnMount={false}
      />,
    );
    expect(unresolvedHtml).toContain("Unable to resolve listed contracts; paper position cannot be marked.");
  });

  it("renders manual close results with gross, commissions, and net values", () => {
    const html = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={setup}
        initialCommissionPerContract={0.65}
        initialOpenResult={{
          order_id: 11,
          position_id: 12,
          market_mode: "options",
          structure_type: "vertical_debit_spread",
          underlying_symbol: "AAPL",
          status: "open",
          order_status: "opened",
          position_status: "open",
          opening_net_debit: 2.4,
          opening_net_credit: null,
          commission_per_contract: 0.65,
          opening_commissions: 1.3,
          max_profit: 760,
          max_loss: 240,
          breakevens: [207.4],
          execution_enabled: false,
          persistence_enabled: true,
          paper_only: true,
          operator_disclaimer: "paper only",
          order_created_at: "2026-04-29T13:00:00Z",
          position_opened_at: "2026-04-29T13:00:00Z",
          legs: [
            {
              id: 101,
              position_id: 12,
              action: "buy",
              right: "call",
              strike: 205,
              expiration: "2026-05-16",
              quantity: 1,
              multiplier: 100,
              entry_premium: 4.2,
              exit_premium: null,
              status: "open",
              label: "Long call",
            },
            {
              id: 102,
              position_id: 12,
              action: "sell",
              right: "call",
              strike: 215,
              expiration: "2026-05-16",
              quantity: 1,
              multiplier: 100,
              entry_premium: 1.8,
              exit_premium: null,
              status: "open",
              label: "Short call",
            },
          ],
        }}
        initialCloseResult={{
          position_id: 12,
          trade_id: 22,
          market_mode: "options",
          structure_type: "vertical_debit_spread",
          underlying_symbol: "AAPL",
          status: "closed",
          position_status: "closed",
          settlement_mode: "manual_close",
          commission_per_contract: 0.65,
          opening_commissions: 1.3,
          closing_commissions: 1.3,
          gross_pnl: 300,
          net_pnl: 297.4,
          total_commissions: 2.6,
          execution_enabled: false,
          persistence_enabled: true,
          paper_only: true,
          operator_disclaimer: "paper only",
          closed_at: "2026-04-29T15:00:00Z",
          legs: [
            {
              id: 201,
              trade_id: 22,
              action: "buy",
              right: "call",
              strike: 205,
              expiration: "2026-05-16",
              quantity: 1,
              multiplier: 100,
              entry_premium: 4.2,
              exit_premium: 6.3,
              leg_gross_pnl: 210,
              leg_commission: 1.3,
              leg_net_pnl: 208.7,
              label: "Long call",
            },
            {
              id: 202,
              trade_id: 22,
              action: "sell",
              right: "call",
              strike: 215,
              expiration: "2026-05-16",
              quantity: 1,
              multiplier: 100,
              entry_premium: 1.8,
              exit_premium: 0.9,
              leg_gross_pnl: 90,
              leg_commission: 1.3,
              leg_net_pnl: 88.7,
              label: "Short call",
            },
          ],
        }}
        loadCommissionOnMount={false}
      />,
    );

    expect(html).toContain("Paper option position manually closed");
    expect(html).toContain("Gross P&amp;L");
    expect(html).toContain("Net P&amp;L");
    expect(html).toContain("Help: Gross P&amp;L");
    expect(html).toContain("Help: Net P&amp;L");
    expect(html).toContain("Help: Total commissions");
    expect(html).toContain("not multiplied by 100");
    expect(html).toContain("$300.00");
    expect(html).toContain("$297.40");
    expect(html).toContain("$2.60");
    expect(html).toContain("This was recorded as a paper options trade. No broker order was sent.");
    expect(html).toContain("Position #12");
    expect(html).toContain("Trade #22");
    expect(html).toContain("Commission is per contract per leg, not multiplied by 100.");
    expect(html).not.toContain("Order #");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
  });

  it("renders source and as-of context when provider metadata is present", () => {
    const html = renderToStaticMarkup(
      <OptionsStructureRiskSummary
        setup={{
          symbol: "SPY",
          market_mode: "options",
          workflow_source: "polygon",
          strategy: "Bull Call Debit Spread",
          option_structure: {
            type: "bull_call_debit_spread",
            expiration: "2026-05-15",
            dte: 16,
            net_debit: 2.4,
            max_profit: 760,
            max_loss: 240,
            breakeven_high: 107.4,
            iv_snapshot: 0.25,
            legs: [
              { action: "buy", right: "call", strike: 105, multiplier: 100, label: "long call" },
              { action: "sell", right: "call", strike: 110, multiplier: 100, label: "short call" },
            ],
          },
          expected_range: {
            status: "computed",
            method: "iv_1sigma",
            reference_price_type: "underlying_last",
            absolute_move: 4.2,
            lower_bound: 101.8,
            upper_bound: 110.2,
            horizon_value: 16,
            horizon_unit: "calendar_days",
            snapshot_timestamp: "2026-04-29T13:00:00Z",
            provenance_notes: "Derived from the current IV snapshot.",
            reason: null,
          },
          options_chain_preview: {
            underlying: "SPY",
            expiry: "2026-05-15",
            calls: [],
            puts: [],
            data_as_of: "2026-04-29T13:01:00Z",
            source: "polygon",
            reason: null,
          },
        }}
        replayPreview={null}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );

    expect(html).toContain("Underlying source");
    expect(html).toContain("Chain preview source");
    expect(html).toContain("Expected Range provenance");
    expect(html).toContain("Expected Range visualization");
    expect(html).toContain("$101.80");
    expect(html).toContain("$110.20");
    expect(html).toContain("2026-04-29 13:00 UTC");
    expect(html).toContain("2026-04-29 13:01 UTC");
    expect(html).toContain("Derived from the current IV snapshot.");
  });

  it("renders recomputed options DTE and expected-range horizon from expiration and as-of", () => {
    const setup: OptionsResearchSetup = {
      symbol: "GOOG",
      market_mode: "options",
      workflow_source: "polygon",
      strategy: "Iron Condor",
      option_structure: {
        type: "iron_condor",
        expiration: "2026-05-16",
        dte: 33,
        dte_as_of: "2026-05-03T14:00:00Z",
        net_credit: 2.5,
        max_profit: 250,
        max_loss: 250,
        breakeven_low: 92.5,
        breakeven_high: 107.5,
        iv_snapshot: 0.24,
        legs: [
          { action: "buy", right: "put", strike: 90, multiplier: 100, label: "lower long put" },
          { action: "sell", right: "put", strike: 95, multiplier: 100, label: "short put" },
          { action: "sell", right: "call", strike: 105, multiplier: 100, label: "short call" },
          { action: "buy", right: "call", strike: 110, multiplier: 100, label: "higher long call" },
        ],
      },
      expected_range: {
        status: "computed" as const,
        method: "iv_1sigma",
        reference_price_type: "underlying_last",
        absolute_move: 4.2,
        lower_bound: 95.8,
        upper_bound: 104.2,
        horizon_value: 33,
        horizon_unit: "calendar_days",
        snapshot_timestamp: "2026-05-03T14:00:00Z",
        provenance_notes: "Derived from the current IV snapshot.",
        reason: null,
      },
      options_chain_preview: null,
    };

    const riskHtml = renderToStaticMarkup(
      <OptionsStructureRiskSummary
        setup={setup}
        replayPreview={null}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );
    const lifecycleHtml = renderToStaticMarkup(
      <OptionsPaperLifecyclePanel
        setup={setup}
        loadCommissionOnMount={false}
      />,
    );

    expect(riskHtml).toContain("DTE 13");
    expect(riskHtml).toContain("over 13 calendar_days");
    expect(riskHtml).not.toContain("DTE 33");
    expect(riskHtml).not.toContain("over 33 calendar_days");
    expect(lifecycleHtml).toContain("DTE:</strong> 13");
    expect(lifecycleHtml).not.toContain("DTE:</strong> 33");
  });

  it("renders safe muted provider-plan guidance for missing source and chain context", () => {
    const html = renderToStaticMarkup(
      <OptionsStructureRiskSummary
        setup={{
          symbol: "NDX",
          market_mode: "options",
          workflow_source: "",
          strategy: "Iron Condor",
          option_structure: {
            type: "iron_condor",
            expiration: "",
            dte: null,
            net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            legs: [{ action: "buy", right: "put", strike: 90, label: "lower long put" }],
          },
          expected_range: {
            status: "omitted",
            method: null,
            reference_price_type: null,
            absolute_move: null,
            lower_bound: null,
            upper_bound: null,
            horizon_value: null,
            horizon_unit: null,
            snapshot_timestamp: null,
            provenance_notes: null,
            reason: "strategy_not_configured_for_expected_range_preview",
          },
          options_chain_preview: null,
        }}
        replayPreview={null}
        paperOpenResult={null}
        paperCloseResult={null}
      />,
    );

    expect(html).toContain("Source unavailable");
    expect(html).toContain("As-of unavailable");
    expect(html).toContain("Chain preview unavailable on current provider plan or payload.");
    expect(html).toContain("Index option research. Cash-settled. No share delivery modeled.");
    expect(html).toContain("Index data entitlement may be required; MacMarket will not silently substitute SPY/QQQ.");
    expect(html).toContain("Expected Range is research context only. It does not modify expiration payoff math.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });
});
