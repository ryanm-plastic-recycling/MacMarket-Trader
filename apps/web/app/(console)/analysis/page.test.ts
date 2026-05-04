import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { GLOSSARY_TERMS } from "@/lib/glossary";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("analysis options provider/source/as-of copy", () => {
  it("keeps options expected range and chain context wired to safe source/as-of fallbacks", () => {
    expect(source).toContain('import { ExpectedRangeVisualization } from "@/components/options/expected-range-visualization";');
    expect(source).toContain('import { MetricLabel } from "@/components/ui/metric-help";');
    expect(source).toContain('import { SYMBOL_ENTRY_HELP_COPY } from "@/lib/symbol-entry";');
    expect(source).toContain("SYMBOL_ENTRY_HELP_COPY.singleSymbolHint");
    expect(source).toContain('<MetricLabel label="Workflow source" term="provider_readiness" />');
    expect(source).toContain('<MetricLabel label="Confidence" term="confidence" />');
    expect(source).toContain('<MetricLabel label="Expected Range status" term="expected_range" />');
    expect(source).toContain('<MetricLabel label="Expected Move" term="expected_range" />');
    expect(source).toContain('<MetricLabel label="DTE" term="dte" />');
    expect(source).toContain('<MetricLabel label="IV snapshot" term="iv" />');
    expect(source).toContain('<MetricLabel label="Breakevens" term="breakeven" />');
    expect(source).toContain('<MetricLabel label="Max profit" term="max_profit" />');
    expect(source).toContain('<MetricLabel label="Max loss" term="max_loss" />');
    expect(source).toContain('formatResearchValue(expectedRange.reference_price_type, "Source unavailable")');
    expect(source).toContain("formatResearchTimestamp(expectedRange.snapshot_timestamp ?? null)");
    expect(source).toContain("formatResearchValue(expectedRange.provenance_notes, \"Source unavailable\")");
    expect(source).toContain("getOptionsResearchDisplayDte(optionStructure, expectedRange)");
    expect(source).toContain("formatOptionsExpectedRangeHorizon(expectedRange, optionStructure)");
    expect(source).toContain("formatExpectedMoveSummary(expectedRange, expectedRangeHorizon)");
    expect(source).toContain("Structure readiness");
    expect(source).toContain("Expected Range readiness");
    expect(source).toContain("Paper Open readiness");
    expect(source).toContain("formatPaperOpenReadiness(paperOpenReadiness)");
    expect(source).toContain("function AnalysisContextPanels");
    expect(source).toContain('Card title="Macro Context"');
    expect(source).toContain('Card title="Index Context"');
    expect(source).toContain('Card title="News Context"');
    expect(source).toContain("Index risk state");
    expect(source).toContain("index_data_stale_or_missing");
    expect(source).toContain('Card title="Selected contract snapshots"');
    expect(source).toContain("Missing from selected contract snapshot");
    expect(source).toContain("Not available from provider");
    expect(source).toContain("leg.implied_volatility");
    expect(source).toContain("leg.open_interest");
    expect(source).toContain("<ExpectedRangeVisualization");
    expect(source).toContain("expectedRange={expectedRange}");
    expect(source).toContain("expectedRange={null}");
    expect(source).toContain("breakevens={optionStructureBreakevens}");
    expect(source).toContain("workflowSource={setup?.workflow_source ?? source}");
    expect(source).toContain("formatResearchValue(optionsChainPreview.source, \"Source unavailable\")");
    expect(source).toContain("formatResearchTimestamp(optionsChainPreview.data_as_of ?? null)");
    expect(source).toContain("Provider plan or payload may not include this data. Index data entitlement may be required for SPX/NDX; MacMarket will not silently substitute SPY/QQQ.");
    expect(source).toContain("Index data entitlement may be required. MacMarket will not silently fall back to an ETF substitute.");
    expect(source).toContain("Source unavailable. As-of unavailable.");
    expect(source).toContain("appliedMarketMode === \"options\"");
    expect(source).toContain("Create recommendation from setup");
    expect(source).not.toContain("stage real order");
    expect(source).not.toContain("broker execution");
    expect(source).not.toContain("probability of profit");
    expect(source).not.toContain("live trading");
  });

  it("keeps Analysis glossary help on safety language", () => {
    expect(GLOSSARY_TERMS.confidence.caveat).not.toMatch(/probability of profit/i);
    expect(GLOSSARY_TERMS.score.caveat).not.toMatch(/probability of profit/i);
    expect(GLOSSARY_TERMS.expected_range.caveat).toMatch(/does not change payoff math/i);
    expect(GLOSSARY_TERMS.expected_range.caveat).toMatch(/approve execution/i);
    expect(GLOSSARY_TERMS.provider_readiness.caveat).toMatch(/not live routing, broker execution/i);
    expect(GLOSSARY_TERMS.provider_readiness.caveat).not.toMatch(/live trading|broker routing/i);
  });
});
