import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "module";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api-client", () => ({
  fetchWorkflowApi: vi.fn(),
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
    ErrorState: ({ title, hint }: { title: string; hint: string }) =>
      ReactModule.createElement("div", {}, `${title} ${hint}`),
    InlineFeedback: ({ message }: { message: string }) =>
      ReactModule.createElement("div", {}, message),
    PageHeader: ({ title, subtitle }: { title: string; subtitle: string }) =>
      ReactModule.createElement("header", {}, `${title} ${subtitle}`),
    StatusBadge: ({ children }: { children: ReactNode }) =>
      ReactModule.createElement("span", {}, children),
  };
});

import SettingsPage from "@/app/(console)/settings/page";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("SettingsPage", () => {
  it("renders explicit options commission guardrails and example copy", () => {
    const html = renderToStaticMarkup(<SettingsPage />);

    expect(html).toContain("Options commission per contract ($)");
    expect(html).toContain("Equity commission per trade");
    expect(html).toContain("Risk budget at stop ($)");
    expect(html).toContain("Max paper order notional ($)");
    expect(html).toContain("max loss at invalidation");
    expect(html).toContain("not a generic trade amount");
    expect(html).toContain("The paper fee applied to each equity paper-trade event.");
    expect(html).toContain("The paper options fee applied per contract, per leg, per open or close event.");
    expect(html).toContain("Not per share. Do not multiply by 100.");
    expect(html).toContain("not multiplied by 100");
    expect(html).toContain("Total options commission = commission per contract x contracts x legs x open/close events.");
    expect(html).toContain("Example: $0.65 commission, 1 iron condor, 4 legs, open + close = $0.65 x 1 x 4 x 2 = $5.20 total estimated commission.");
  });
});
