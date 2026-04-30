import React from "react";
import type { ReactNode } from "react";
import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";

import { SymbolEntryPreview } from "@/components/symbol-entry-preview";
import { parseManualSymbolEntry } from "@/lib/symbol-entry";

const require = createRequire(import.meta.url);
const { renderToStaticMarkup } = require("react-dom/server") as {
  renderToStaticMarkup: (element: ReactNode) => string;
};

describe("SymbolEntryPreview", () => {
  it("renders normalized uppercase symbols and duplicate warnings", () => {
    const parsed = parseManualSymbolEntry("spy, qqq, spy");
    const html = renderToStaticMarkup(<SymbolEntryPreview parsed={parsed} />);

    expect(html).toContain("Parsed symbols:");
    expect(html).toContain("SPY, QQQ");
    expect(html).toContain("2 symbols - 1 duplicate ignored");
    expect(html).toContain("Blank separators ignored.");
    expect(html).toContain("Duplicate ignored: SPY");
    expect(html).not.toContain("null");
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("NaN");
    expect(html).not.toContain("Infinity");
  });
});
