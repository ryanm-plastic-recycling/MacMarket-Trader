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

import {
  OPTIONS_COMMISSION_FORMULA_COPY,
  OPTIONS_COMMISSION_REMINDER_COPY,
  OPTIONS_DURABLE_PURPOSE_COPY,
  OPTIONS_DURABLE_SOURCE_CONTEXT_NOTE,
  PaperOptionsPositionsSectionContent,
} from "@/components/orders/paper-options-positions-section";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("PaperOptionsPositionsSectionContent", () => {
  it("explains display-only durable paper option lifecycle records", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading={false}
        error={null}
        items={[]}
      />,
    );

    expect(html).toContain("Paper options positions");
    expect(html).toContain("Durable paper lifecycle records");
    expect(html).toContain("No broker orders were sent");
    expect(html).toContain("Display-only");
    expect(html).toContain(OPTIONS_DURABLE_PURPOSE_COPY);
    expect(html).toContain(OPTIONS_DURABLE_SOURCE_CONTEXT_NOTE);
    expect(html).toContain("Provider/source context may be limited on durable lifecycle rows.");
    expect(html).toContain("Source unavailable / As-of unavailable here is not a lifecycle error.");
    expect(html).toContain(OPTIONS_COMMISSION_REMINDER_COPY);
    expect(html).toContain(OPTIONS_COMMISSION_FORMULA_COPY);
    expect(html).toContain("Help: Options commission");
    expect(html).toContain("The paper options fee applied per contract, per leg, per open or close event.");
    expect(html).toContain("Not per share and not multiplied by 100.");
    expect(html).toContain("No paper options positions yet");
    expect(html).not.toContain("live trading");
    expect(html).not.toContain("live routing");
    expect(html).not.toContain("broker execution");
    expect(html).not.toContain("real-money routing");
    expect(html).not.toContain("staged brokerage order");
    expect(html).not.toContain("assignment/exercise support");
    expect(html).not.toContain("expiration settlement support");
  });

  it("renders open and closed paper option lifecycle rows with key fields", () => {
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
            opening_commissions: 1.3,
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

    expect(html).toContain("Open paper positions");
    expect(html).toContain("Manually closed paper positions");
    expect(html).toContain("Help: Open paper positions");
    expect(html).toContain("Help: Manually closed paper positions");
    expect(html).toContain("Paper lifecycle records do not mean external orders were sent.");
    expect(html).toContain("Open paper position");
    expect(html).toContain("Manually closed paper position");
    expect(html).toContain("AAPL");
    expect(html).toContain("Vertical Debit Spread");
    expect(html).toContain("Debit $2.60");
    expect(html).toContain("$740.00");
    expect(html).toContain("$260.00");
    expect(html).toContain("$207.60");
    expect(html).toContain("Not final");
    expect(html).toContain("Gross, commissions, and net paper result appear after manual close.");
    expect(html).toContain("SPY");
    expect(html).toContain("Iron Condor");
    expect(html).toContain("Credit $2.50");
    expect(html).toContain("Position #22");
    expect(html).toContain("Trade #77");
    expect(html).toContain("Manual close recorded");
    expect(html).toContain("$180.00");
    expect(html).toContain("$2.60");
    expect(html).toContain("$5.20");
    expect(html).toContain("$174.80");
    expect(html).toContain("Help: Max profit");
    expect(html).toContain("Help: Max loss");
    expect(html).toContain("Help: Breakevens");
    expect(html).toContain("Help: Gross P&amp;L");
    expect(html).toContain("Help: Net P&amp;L");
    expect(html).toContain("Help: Total commissions");
    expect(html).toContain("Paper profit or loss before commissions are subtracted.");
    expect(html).toContain("Paper profit or loss after modeled commissions are subtracted.");
    expect(html).toContain("Paper-only");
    expect(html).toContain("execution_enabled=false");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("null");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });

  it("recomputes lifecycle DTE from expiration and as-of date", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading={false}
        error={null}
        asOf="2026-05-03T14:00:00Z"
        items={[
          {
            position_id: 42,
            trade_id: null,
            market_mode: "options",
            underlying_symbol: "GOOG",
            structure_type: "iron_condor",
            status: "open",
            expiration: "2026-05-16",
            opened_at: "2026-05-03T14:00:00Z",
            closed_at: null,
            source_order_id: null,
            contract_count: 1,
            leg_count: 4,
            opening_net_debit: null,
            opening_net_credit: 2.5,
            max_profit: 250,
            max_loss: 250,
            breakevens: [92.5, 107.5],
            settlement_mode: null,
            gross_pnl: null,
            opening_commissions: 2.6,
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

    expect(html).toContain("2026-05-16");
    expect(html).toContain("DTE:</strong> 13");
    expect(html).not.toContain("DTE:</strong> 33");
  });

  it("renders leg detail columns for open and closed lifecycle rows", () => {
    const html = renderToStaticMarkup(
      <PaperOptionsPositionsSectionContent
        loading={false}
        error={null}
        items={[
          {
            position_id: 31,
            trade_id: 32,
            market_mode: "options",
            underlying_symbol: "MSFT",
            structure_type: "vertical_debit_spread",
            status: "closed",
            expiration: "2026-05-15",
            opened_at: "2026-04-29T13:00:00Z",
            closed_at: "2026-04-29T15:00:00Z",
            source_order_id: 15,
            contract_count: 1,
            leg_count: 2,
            opening_net_debit: 2.5,
            opening_net_credit: null,
            max_profit: 250,
            max_loss: 250,
            breakevens: [102.5],
            settlement_mode: "manual_close",
            gross_pnl: 120,
            opening_commissions: 1.3,
            closing_commissions: 1.3,
            total_commissions: 2.6,
            net_pnl: 117.4,
            execution_enabled: false,
            persistence_enabled: true,
            paper_only: true,
            operator_disclaimer: "paper only",
            legs: [
              {
                action: "buy",
                right: "call",
                strike: 100,
                expiration: "2026-05-15",
                quantity: 1,
                multiplier: 100,
                entry_premium: 4.2,
                exit_premium: 5.8,
                status: "closed",
                label: "Long call",
                leg_gross_pnl: 160,
                leg_commission: 1.3,
                leg_net_pnl: 158.7,
              },
            ],
          },
        ]}
      />,
    );

    expect(html).toContain("action");
    expect(html).toContain("right");
    expect(html).toContain("strike");
    expect(html).toContain("entry premium");
    expect(html).toContain("exit premium");
    expect(html).toContain("leg gross");
    expect(html).toContain("leg commission");
    expect(html).toContain("leg net");
    expect(html).toContain("Help: leg gross");
    expect(html).toContain("Help: leg commission");
    expect(html).toContain("Help: leg net");
    expect(html).toContain("buy");
    expect(html).toContain("CALL");
    expect(html).toContain("100");
    expect(html).toContain("1 contract");
    expect(html).toContain("$4.20");
    expect(html).toContain("$5.80");
    expect(html).toContain("$160.00");
    expect(html).toContain("$158.70");
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
            leg_count: 0,
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
