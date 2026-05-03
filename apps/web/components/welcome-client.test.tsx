import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "module";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { WelcomeClient } from "@/components/welcome-client";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("WelcomeClient", () => {
  it("renders the quick-start cheat sheet and current safety boundaries", () => {
    const markdown = readFileSync(resolve(process.cwd(), "..", "..", "docs", "alpha-user-welcome.md"), "utf8");
    const html = renderToStaticMarkup(<WelcomeClient markdown={markdown} />);

    expect(html).toContain("MacMarket Quick Start");
    expect(html).toContain("research and paper-trading console");
    expect(html).toContain("No live trading");
    expect(html).toContain("No broker routing");
    expect(html).toContain("Provider Health");
    expect(html).toContain("Market Risk Today");
    expect(html).toContain("Refresh the");
    expect(html).toContain("Recommendations");
    expect(html).toContain("Opportunity Intelligence");
    expect(html).toContain("risk-at-stop");
    expect(html).toContain("Active Position Review");
    expect(html).toContain("Option marks");
    expect(html).toContain("provider entitlement");
    expect(html).toContain("mark_unavailable");
    expect(html).toContain("Deterministic engines own approval");
    expect(html).toContain("paper order creation");
    expect(html).not.toContain("live broker routing");
    expect(html).not.toContain("automatic live execution");
  });
});
