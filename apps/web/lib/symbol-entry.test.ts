import { describe, expect, it } from "vitest";

import { parseManualSymbolEntry, SYMBOL_ENTRY_HELP_COPY } from "@/lib/symbol-entry";

describe("manual symbol entry helpers", () => {
  it("normalizes comma, space, and newline separated symbols", () => {
    const parsed = parseManualSymbolEntry(" spy, qqq\nAAPL msft ");

    expect(parsed.symbols).toEqual(["SPY", "QQQ", "AAPL", "MSFT"]);
    expect(parsed.duplicateCount).toBe(0);
  });

  it("deduplicates preview symbols while tracking ignored duplicates", () => {
    const parsed = parseManualSymbolEntry("spy, SPY qqq\nQQQ aapl");

    expect(parsed.symbols).toEqual(["SPY", "QQQ", "AAPL"]);
    expect(parsed.duplicates).toEqual(["SPY", "QQQ"]);
    expect(parsed.duplicateCount).toBe(2);
  });

  it("keeps operator guidance manual and non-executional", () => {
    const copy = JSON.stringify(SYMBOL_ENTRY_HELP_COPY).toLowerCase();

    expect(SYMBOL_ENTRY_HELP_COPY.separators).toContain("commas, spaces, or new lines");
    expect(SYMBOL_ENTRY_HELP_COPY.substitutes).toContain("SPY/QQQ");
    expect(SYMBOL_ENTRY_HELP_COPY.temporaryUniverse).toContain("temporary manual universe");
    expect(copy).not.toContain("live trading");
    expect(copy).not.toContain("broker routing");
    expect(copy).not.toContain("execution approval");
  });
});
