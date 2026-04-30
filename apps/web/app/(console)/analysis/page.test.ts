import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("analysis options provider/source/as-of copy", () => {
  it("keeps options expected range and chain context wired to safe source/as-of fallbacks", () => {
    expect(source).toContain('import { ExpectedRangeVisualization } from "@/components/options/expected-range-visualization";');
    expect(source).toContain('formatResearchValue(expectedRange.reference_price_type, "Source unavailable")');
    expect(source).toContain("formatResearchTimestamp(expectedRange.snapshot_timestamp ?? null)");
    expect(source).toContain("formatResearchValue(expectedRange.provenance_notes, \"Source unavailable\")");
    expect(source).toContain("<ExpectedRangeVisualization");
    expect(source).toContain("expectedRange={expectedRange}");
    expect(source).toContain("expectedRange={null}");
    expect(source).toContain("breakevens={optionStructureBreakevens}");
    expect(source).toContain("workflowSource={setup?.workflow_source ?? source}");
    expect(source).toContain("formatResearchValue(optionsChainPreview.source, \"Source unavailable\")");
    expect(source).toContain("formatResearchTimestamp(optionsChainPreview.data_as_of ?? null)");
    expect(source).toContain("Provider plan or payload may not include this data. SPX/NDX may require index data access; SPY/QQQ can be practical ETF substitutes.");
    expect(source).toContain("Source unavailable. As-of unavailable.");
    expect(source).toContain("appliedMarketMode === \"options\"");
    expect(source).toContain("Create recommendation from setup");
    expect(source).not.toContain("stage real order");
    expect(source).not.toContain("broker execution");
    expect(source).not.toContain("probability of profit");
    expect(source).not.toContain("live trading");
  });
});
