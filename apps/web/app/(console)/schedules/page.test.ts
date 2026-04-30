import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("schedules manual symbol entry cleanup", () => {
  it("adds helper copy and parsed previews to schedule and watchlist symbol entry", () => {
    expect(source).toContain('import { SymbolEntryPreview } from "@/components/symbol-entry-preview";');
    expect(source).toContain('import { parseManualSymbolEntry, SYMBOL_ENTRY_HELP_COPY } from "@/lib/symbol-entry";');
    expect(source).toContain("const parsedScheduleSymbols = useMemo(() => parseManualSymbolEntry(symbols), [symbols]);");
    expect(source).toContain("const parsedWatchlistSymbols = useMemo(() => parseManualSymbolEntry(wlSymbols), [wlSymbols]);");
    expect(source).toContain("<span>Symbols to evaluate</span>");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.separators");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.substitutes");
    expect(source).toContain("<SymbolEntryPreview parsed={parsedScheduleSymbols} />");
    expect(source).toContain("<SymbolEntryPreview parsed={parsedWatchlistSymbols} />");
    expect(source).toContain("symbols: parsedScheduleSymbols.symbols");
    expect(source).toContain("symbols: parsedWatchlistSymbols.symbols");
  });

  it("does not add provider search or execution language to schedules", () => {
    expect(source).not.toContain("provider symbol search");
    expect(source).not.toContain("broker routing");
    expect(source).not.toContain("live trading");
    expect(source).not.toContain("execution approval");
  });
});
