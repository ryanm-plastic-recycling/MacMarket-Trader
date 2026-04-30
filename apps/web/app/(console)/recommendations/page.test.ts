import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { GLOSSARY_TERMS } from "@/lib/glossary";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

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
