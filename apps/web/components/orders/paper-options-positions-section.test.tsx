import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "module";
import { describe, expect, it, vi } from "vitest";

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

import { PaperOptionsPositionsSectionContent } from "@/components/orders/paper-options-positions-section";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("PaperOptionsPositionsSectionContent", () => {
  it("renders open and closed paper option lifecycle rows safely", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading={false}
        error={null}
        items={[
          {
            position_id: 12,
            trade_id: null,
            market_mode: "options",
            underlying_symbol: "AAPL",
            structure_type: "vertical_debit_spread",
            status: "open",
            expiration: "2026-05-15",
            opened_at: "2026-04-29T13:00:00Z",
            closed_at: null,
            source_order_id: 5,
            contract_count: 1,
            leg_count: 2,
            opening_net_debit: 2.6,
            opening_net_credit: null,
            max_profit: 740,
            max_loss: 260,
            breakevens: [207.6],
            settlement_mode: null,
            gross_pnl: null,
            opening_commissions: null,
            closing_commissions: null,
            total_commissions: null,
            net_pnl: null,
            execution_enabled: false,
            persistence_enabled: true,
            paper_only: true,
            operator_disclaimer: "paper only",
            legs: [
              {
                action: "buy",
                right: "call",
                strike: 205,
                expiration: "2026-05-15",
                quantity: 1,
                multiplier: 100,
                entry_premium: 4.2,
                exit_premium: null,
                status: "open",
                label: "Long call",
              },
              {
                action: "sell",
                right: "call",
                strike: 215,
                expiration: "2026-05-15",
                quantity: 1,
                multiplier: 100,
                entry_premium: 1.6,
                exit_premium: null,
                status: "open",
                label: "Short call",
              },
            ],
          },
          {
            position_id: 22,
            trade_id: 77,
            market_mode: "options",
            underlying_symbol: "SPY",
            structure_type: "iron_condor",
            status: "closed",
            expiration: "2026-05-15",
            opened_at: "2026-04-29T13:00:00Z",
            closed_at: "2026-04-29T15:00:00Z",
            source_order_id: 15,
            contract_count: 1,
            leg_count: 4,
            opening_net_debit: null,
            opening_net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            breakevens: [92.5, 107.5],
            settlement_mode: "manual_close",
            gross_pnl: 180,
            opening_commissions: 2.6,
            closing_commissions: 2.6,
            total_commissions: 5.2,
            net_pnl: 174.8,
            execution_enabled: false,
            persistence_enabled: true,
            paper_only: true,
            operator_disclaimer: "paper only",
            legs: [
              {
                action: "buy",
                right: "put",
                strike: 90,
                expiration: "2026-05-15",
                quantity: 1,
                multiplier: 100,
                entry_premium: 1.1,
                exit_premium: 0.8,
                status: "closed",
                label: "Long put wing",
                leg_gross_pnl: -30,
                leg_commission: 1.3,
                leg_net_pnl: -31.3,
              },
            ],
          },
        ]}
      />,
    );

    expect(html).toContain("Paper Options Positions");
    expect(html).toContain("Paper-only");
    expect(html).toContain("Open paper options positions");
    expect(html).toContain("Closed paper options positions");
    expect(html).toContain("Pending manual paper close");
    expect(html).toContain("Gross, commissions, and net paper result appear after manual close.");
    expect(html).toContain("Position #22");
    expect(html).toContain("Trade #77");
    expect(html).toContain("$180.00");
    expect(html).toContain("$174.80");
    expect(html).toContain("$5.20");
    expect(html).toContain("Separate from equity orders and replay payoff preview.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
    expect(html).not.toContain("live trading");
    expect(html).not.toContain("broker execution");
  });

  it("renders empty and missing values safely", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading={false}
        error={null}
        items={[]}
      />,
    );

    expect(html).toContain("No paper options positions yet");
    expect(html).toContain("Save as paper option position");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
  });

  it("renders loading and error states safely", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading
        error="Authentication required"
        items={[]}
        onRetry={() => {}}
      />,
    );

    expect(html).toContain("Loading paper options positions");
    expect(html).toContain("Failed to load paper options positions");
    expect(html).toContain("Authentication required");
    expect(html).toContain("Retry paper options load");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });

  it("renders safe missing-value fallbacks for closed rows", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading={false}
        error={null}
        items={[
          {
            position_id: 90,
            trade_id: 91,
            market_mode: "options",
            underlying_symbol: "QQQ",
            structure_type: "long_call",
            status: "closed",
            expiration: null,
            opened_at: "2026-04-29T13:00:00Z",
            closed_at: null,
            source_order_id: null,
            contract_count: null,
            leg_count: 1,
            opening_net_debit: null,
            opening_net_credit: null,
            max_profit: null,
            max_loss: null,
            breakevens: [],
            settlement_mode: "manual_close",
            gross_pnl: null,
            opening_commissions: null,
            closing_commissions: null,
            total_commissions: null,
            net_pnl: null,
            execution_enabled: false,
            persistence_enabled: true,
            paper_only: true,
            operator_disclaimer: "paper only",
            legs: [],
          },
        ]}
      />,
    );

    expect(html).toContain("Unavailable");
    expect(html).toContain("—");
    expect(html).toContain("Leg detail unavailable.");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });
});
