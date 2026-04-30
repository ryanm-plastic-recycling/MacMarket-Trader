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

describe("watchlist table polish", () => {
  it("adds searchable and sortable watchlist management around existing symbol arrays", () => {
    expect(source).toContain('type WatchlistSort = "name" | "symbol_count";');
    expect(source).toContain("const [watchlistQuery, setWatchlistQuery] = useState(\"\");");
    expect(source).toContain('const [watchlistSort, setWatchlistSort] = useState<WatchlistSort>("name");');
    expect(source).toContain("const visibleWatchlists = useMemo(() => {");
    expect(source).toContain("Search watchlists");
    expect(source).toContain("Sort watchlists");
    expect(source).toContain('<option value="symbol_count">symbol count</option>');
    expect(source).toContain("Existing watchlist storage");
    expect(source).toContain("Current lists keep existing symbol-array storage");
  });

  it("renders normalized symbol chips with counts, duplicate feedback, and per-list filtering", () => {
    expect(source).toContain("const parsed = parseManualSymbolEntry((wl.symbols ?? []).join(\",\"));");
    expect(source).toContain("Filter symbols in this list");
    expect(source).toContain("{parsed.symbols.length} symbol");
    expect(source).toContain("Duplicate ignored in preview");
    expect(source).toContain("shownSymbols.length ? shownSymbols.map((symbol) => (");
    expect(source).toContain('className="op-badge op-badge-neutral"');
  });

  it("supports individual symbol removal through the existing watchlist update route", () => {
    expect(source).toContain("async function removeWatchlistSymbol(wl: Watchlist, symbol: string)");
    expect(source).toContain("const nextSymbols = parsed.symbols.filter((item) => item !== symbol);");
    expect(source).toContain("Watchlists need at least one symbol. Delete the watchlist instead.");
    expect(source).toContain("method: \"PUT\"");
    expect(source).toContain("body: JSON.stringify({ symbols: nextSymbols })");
    expect(source).toContain("aria-label={`Remove ${symbol} from ${wl.name}`}");
  });

  it("keeps watchlist copy scoped to research-universe management", () => {
    expect(source).toContain("Research universe only; watchlists organize symbols for scans and do not send orders.");
    expect(source).toContain("Provider metadata may be unavailable; manual symbols can still be saved.");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.substitutes");
    expect(source).not.toContain("broker execution");
    expect(source).not.toContain("brokerage routing");
    expect(source).not.toContain("live trading");
  });
});
