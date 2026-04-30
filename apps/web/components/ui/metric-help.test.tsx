import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "module";
import { describe, expect, it } from "vitest";

import { MetricHelp, MetricLabel } from "@/components/ui/metric-help";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("MetricHelp", () => {
  it("renders a known glossary term with accessible summary help", () => {
    const html = renderToStaticMarkup(<MetricHelp term="rr" />);

    expect(html).toContain("Help: RR");
    expect(html).toContain("Risk-reward ratio");
    expect(html).toContain("expected reward / planned risk");
  });

  it("renders a label plus metric help", () => {
    const html = renderToStaticMarkup(<MetricLabel label="Expected Range" term="expected_range" />);

    expect(html).toContain("Expected Range");
    expect(html).toContain("Expected Range / Expected Move");
    expect(html).toContain("does not change payoff math");
  });

  it("renders nothing for an unknown term instead of crashing", () => {
    const html = renderToStaticMarkup(<MetricHelp term="does_not_exist" />);

    expect(html).toBe("");
  });
});
