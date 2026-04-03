import { fetchWorkflowApi } from "@/lib/api-client";

export type MarketMode = "equities" | "options" | "crypto";

export type StrategyRegistryEntry = {
  strategy_id: string;
  display_name: string;
  market_mode: MarketMode;
  status: "live" | "planned" | "research_only";
  summary: string;
  directional_profile: "bullish" | "bearish" | "neutral" | "carry" | "volatility";
  execution_readiness: string;
  required_data_inputs: string[];
  operator_notes: string[];
};

export function filterStrategiesByMode(entries: StrategyRegistryEntry[], mode: MarketMode): StrategyRegistryEntry[] {
  return entries.filter((entry) => entry.market_mode === mode);
}

export async function fetchStrategyRegistry(mode?: MarketMode): Promise<StrategyRegistryEntry[]> {
  const suffix = mode ? `?market_mode=${encodeURIComponent(mode)}` : "";
  const result = await fetchWorkflowApi<StrategyRegistryEntry>(`/api/user/strategy-registry${suffix}`);
  if (!result.ok) {
    throw new Error(result.error ?? "Failed to fetch strategy registry");
  }
  return result.items;
}
