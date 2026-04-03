import { describe, expect, it } from "vitest";

import { filterStrategiesByMode, type StrategyRegistryEntry } from "@/lib/strategy-registry";

const FIXTURE: StrategyRegistryEntry[] = [
  {
    strategy_id: "event_continuation",
    display_name: "Event Continuation",
    market_mode: "equities",
    status: "live",
    summary: "",
    directional_profile: "bullish",
    execution_readiness: "live",
    required_data_inputs: [],
    operator_notes: [],
  },
  {
    strategy_id: "iron_condor",
    display_name: "Iron Condor",
    market_mode: "options",
    status: "research_only",
    summary: "",
    directional_profile: "neutral",
    execution_readiness: "planned_research_preview",
    required_data_inputs: [],
    operator_notes: [],
  },
];

describe("filterStrategiesByMode", () => {
  it("returns only strategies for selected market mode", () => {
    expect(filterStrategiesByMode(FIXTURE, "equities")).toHaveLength(1);
    expect(filterStrategiesByMode(FIXTURE, "options")[0]?.strategy_id).toBe("iron_condor");
  });
});
