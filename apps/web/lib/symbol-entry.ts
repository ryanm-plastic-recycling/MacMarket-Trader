export type ParsedManualSymbols = {
  rawSymbols: string[];
  symbols: string[];
  duplicates: string[];
  duplicateCount: number;
};

export const SYMBOL_ENTRY_HELP_COPY = {
  separators: "Enter tickers separated by commas, spaces, or new lines.",
  example: "Example: SPY, QQQ, AAPL, MSFT",
  substitutes: "Use SPY/QQQ as ETF substitutes when index data for SPX/NDX is unavailable.",
  temporaryUniverse: "This is a temporary manual universe until watchlist management is implemented.",
  futureWatchlists: "Future watchlist management will add search, filters, active/inactive symbols, tags, and bulk import.",
  singleSymbolHint: "Use ticker symbols such as SPY, QQQ, AAPL. Index symbols such as SPX may require index data access.",
} as const;

export function parseManualSymbolEntry(value: string): ParsedManualSymbols {
  const rawSymbols = value
    .split(/[,\s]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);

  const seen = new Set<string>();
  const duplicateSet = new Set<string>();
  const symbols: string[] = [];

  for (const symbol of rawSymbols) {
    if (seen.has(symbol)) {
      duplicateSet.add(symbol);
      continue;
    }
    seen.add(symbol);
    symbols.push(symbol);
  }

  return {
    rawSymbols,
    symbols,
    duplicates: Array.from(duplicateSet),
    duplicateCount: rawSymbols.length - symbols.length,
  };
}

export function formatParsedSymbols(parsed: ParsedManualSymbols): string {
  return parsed.symbols.length ? parsed.symbols.join(", ") : "-";
}

export function formatParsedSymbolCount(parsed: ParsedManualSymbols): string {
  const symbolLabel = `${parsed.symbols.length} symbol${parsed.symbols.length === 1 ? "" : "s"}`;
  if (!parsed.duplicateCount) return symbolLabel;
  const duplicateLabel = `${parsed.duplicateCount} duplicate${parsed.duplicateCount === 1 ? "" : "s"} ignored`;
  return `${symbolLabel} - ${duplicateLabel}`;
}
