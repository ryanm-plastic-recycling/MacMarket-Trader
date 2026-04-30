import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "module";
import { describe, expect, it } from "vitest";

import { ExpectedRangeVisualization } from "@/components/options/expected-range-visualization";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("ExpectedRangeVisualization", () => {
  it("renders a computed expected range with lower, upper, breakeven, and provenance labels", () => {
    const html = renderToStaticMarkup(
      <ExpectedRangeVisualization
        expectedRange={{
          status: "computed",
          method: "iv_1sigma",
          reference_price_type: "underlying_last",
          absolute_move: 5,
          lower_bound: 95,
          upper_bound: 105,
          horizon_value: 16,
          horizon_unit: "calendar_days",
          snapshot_timestamp: "2026-04-29T13:00:00Z",
          provenance_notes: "Derived from available IV snapshot.",
          reason: null,
        }}
        breakevens={[97.5, 106]}
        expiration="2026-05-15"
        dte={16}
        maxProfit={250}
        maxLoss={240}
        workflowSource="polygon"
      />,
    );

    expect(html).toContain("Expected Range visualization");
    expect(html).toContain("Lower");
    expect(html).toContain("$95.00");
    expect(html).toContain("Upper");
    expect(html).toContain("$105.00");
    expect(html).toContain("Breakeven 1");
    expect(html).toContain("Breakeven 2");
    expect(html).toContain("Range midpoint");
    expect(html).toContain("$100.00");
    expect(html).toContain("$97.50 / $106.00");
    expect(html).toContain("Breakeven outside expected range: $106.00.");
    expect(html).toContain("IV 1sigma");
    expect(html).toContain("2026-04-29 13:00 UTC");
    expect(html).toContain("Derived from available IV snapshot.");
  });

  it("labels explicit current price separately from derived range midpoint", () => {
    const html = renderToStaticMarkup(
      <ExpectedRangeVisualization
        expectedRange={{
          status: "computed",
          method: "iv_move",
          absolute_move: 4,
          lower_bound: 96,
          upper_bound: 104,
        }}
        currentPrice={101}
      />,
    );

    expect(html).toContain("Current");
    expect(html).toContain("$101.00");
    expect(html).not.toContain("Range midpoint");
  });

  it("renders blocked expected range reasons in a muted unavailable state", () => {
    const html = renderToStaticMarkup(
      <ExpectedRangeVisualization
        expectedRange={{
          status: "blocked",
          method: null,
          lower_bound: null,
          upper_bound: null,
          absolute_move: null,
          reason: "missing_iv_snapshot",
        }}
      />,
    );

    expect(html).toContain("Unavailable. missing_iv_snapshot");
    expect(html).toContain("Expected Range is research context only. It does not change payoff math or approve execution.");
    expect(html).not.toContain("Breakeven 1");
  });

  it("renders missing expected range safely without unsafe numeric output", () => {
    const html = renderToStaticMarkup(
      <ExpectedRangeVisualization
        expectedRange={null}
        breakevens={[Number.NaN, Number.POSITIVE_INFINITY]}
        currentPrice={Number.NEGATIVE_INFINITY}
        referencePrice={Number.NaN}
        maxProfit={Number.POSITIVE_INFINITY}
        maxLoss={Number.NaN}
      />,
    );

    expect(html).toContain("Unavailable. Expected Range unavailable.");
    expect(html).not.toContain("null");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });

  it("keeps safety copy research-only without probability or routing claims", () => {
    const html = renderToStaticMarkup(
      <ExpectedRangeVisualization
        expectedRange={{
          status: "computed",
          method: "iv_move",
          absolute_move: 4,
          lower_bound: 96,
          upper_bound: 104,
          snapshot_timestamp: "",
        }}
        breakevens={[100]}
        workflowSource=""
      />,
    );

    expect(html).toContain("Expected Range is research context only.");
    expect(html).toContain("It does not change payoff math or approve execution.");
    expect(html).toContain("does not change payoff math, approve execution, or represent probability of profit.");
    expect(html).toContain("Range is based on available provider data and assumptions.");
    expect(html).toContain("Source unavailable");
    expect(html).toContain("As-of unavailable");
    expect(html).not.toContain("chance of winning");
    expect(html).not.toContain("execution approved");
    expect(html).not.toContain("trade signal");
    expect(html).not.toContain("live trading");
    expect(html).not.toContain("broker order");
    expect(html).not.toContain("route order");
  });
});
