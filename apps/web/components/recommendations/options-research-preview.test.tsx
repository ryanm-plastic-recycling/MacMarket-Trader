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

import { OptionsReplayPreviewPanel } from "@/components/recommendations/options-research-preview";
import type {
  OptionsReplayPreviewAvailability,
  OptionsReplayPreviewResponse,
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

    expect(html).toContain("Options replay preview — expiration payoff only");
    expect(html).toContain("Vertical Debit Spread");
    expect(html).toContain("$600.00");
    expect(html).toContain("$400.00");
    expect(html).toContain("$104.00");
    expect(html).toContain("Expiration payoff table");
    expect(html).toContain("$0.00");
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
