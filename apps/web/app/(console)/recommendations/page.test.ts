import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { GLOSSARY_TERMS } from "@/lib/glossary";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");
const previewProxySource = readFileSync(new URL("../../api/user/symbol-universe/preview/route.ts", import.meta.url), "utf8");

describe("recommendations metric help rollout", () => {
  it("adds clearer manual symbol-entry guidance and parsed preview wiring", () => {
    expect(source).toContain('import { SymbolEntryPreview } from "@/components/symbol-entry-preview";');
    expect(source).toContain('import { parseManualSymbolEntry, SYMBOL_ENTRY_HELP_COPY } from "@/lib/symbol-entry";');
    expect(source).toContain("const parsedSymbols = useMemo(() => parseManualSymbolEntry(symbols), [symbols]);");
    expect(source).toContain('<Card title="Recommendation universe">');
    expect(source).toContain("<span>Symbols to evaluate</span>");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.separators");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.example");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.substitutes");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.temporaryUniverse");
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.futureWatchlists");
    expect(source).toContain("<SymbolEntryPreview parsed={parsedSymbols} />");
    expect(source).toContain('body: JSON.stringify({ symbols: activeSymbols, timeframe: "1D", market_mode: "equities" })');
  });

  it("adds a read-only recommendation-universe selector and preview proxy", () => {
    expect(source).toContain('type UniverseSourceType = "manual" | "watchlist" | "watchlist_plus_manual" | "all_active";');
    expect(source).toContain('const [universeMode, setUniverseMode] = useState<UniverseSourceType>("manual");');
    expect(source).toContain('const [watchlists, setWatchlists] = useState<RecommendationWatchlist[]>([]);');
    expect(source).toContain('"/api/user/watchlists"');
    expect(source).toContain('"/api/user/symbol-universe/preview"');
    expect(source).toContain('<option value="manual">Manual symbols</option>');
    expect(source).toContain('<option value="watchlist">Saved watchlist</option>');
    expect(source).toContain('<option value="watchlist_plus_manual">Watchlist + manual additions</option>');
    expect(source).toContain('<option value="all_active">All active symbols</option>');
    expect(source).toContain("This preview does not submit recommendations.");
    expect(source).toContain("Provider metadata may be unavailable.");
    expect(previewProxySource).toContain('backendPath: "/user/symbol-universe/preview"');
  });

  it("keeps universe preview separate from queue submit until explicitly applied", () => {
    expect(source).toContain("async function previewUniverse()");
    expect(source).toContain("function applyResolvedSymbols()");
    expect(source).toContain('setSymbols(universePreview.resolved_symbols.join(", "));');
    expect(source).toContain("Refresh queue still uses the manual path.");
    expect(source).toContain("Preview universe");
    expect(source).toContain("Use resolved symbols");
    expect(source).toContain('body: JSON.stringify(payload)');
    expect(source).toContain('body: JSON.stringify({ symbols: activeSymbols, timeframe: "1D", market_mode: "equities" })');
  });

  it("renders preview count, duplicate, exclusion, pinned, and warning context safely", () => {
    expect(source).toContain("universePreview.symbol_count");
    expect(source).toContain("universePreview.duplicates_ignored");
    expect(source).toContain("universePreview.exclusions_applied");
    expect(source).toContain("universePreview.pinned_symbols_applied");
    expect(source).toContain("universePreview.warnings.map(formatUniverseWarning)");
    expect(source).toContain("No symbols resolved for this preview.");
    expect(source).toContain('universePreview.resolved_symbols.length ? universePreview.resolved_symbols.join(", ") : "—"');
  });

  it("keeps unsafe routing language out of the universe selector copy", () => {
    const selectorStart = source.indexOf('      {showExecutionCtas ? <Card title="Recommendation universe">');
    const selectorEnd = source.indexOf('      {showExecutionCtas && error ?', selectorStart);
    const selectorSource = source.slice(selectorStart, selectorEnd).toLowerCase();

    expect(selectorSource).not.toContain("live trading");
    expect(selectorSource).not.toContain("broker execution");
    expect(selectorSource).not.toContain("broker routing");
    expect(selectorSource).not.toContain("real-money");
  });

  it("adds compact score, confidence, and RR help to queue and detail labels", () => {
    expect(source).toContain('import { MetricLabel } from "@/components/ui/metric-help";');
    expect(source).toContain('<MetricLabel label="score" term="score" />');
    expect(source).toContain('<MetricLabel label="rr" term="rr" />');
    expect(source).toContain('<MetricLabel label="conf" term="confidence" />');
    expect(source).toContain('<MetricLabel label="expected rr" term="rr" />');
    expect(source).toContain('<MetricLabel label="confidence" term="confidence" />');
    expect(source).toContain('<MetricLabel label="risk score" term="score" />');
    expect(source).toContain('<MetricLabel label="queue score" term="score" />');
  });

  it("keeps score and confidence glossary copy away from probability or execution claims", () => {
    const confidenceCopy = JSON.stringify(GLOSSARY_TERMS.confidence).toLowerCase();
    const scoreCopy = JSON.stringify(GLOSSARY_TERMS.score).toLowerCase();

    expect(confidenceCopy).not.toContain("probability of profit");
    expect(scoreCopy).not.toContain("probability of profit");
    expect(confidenceCopy).not.toContain("broker execution");
    expect(scoreCopy).not.toContain("broker routing");
    expect(scoreCopy).toContain("not a broker signal");
    expect(scoreCopy).toContain("execution approval");
  });
});
