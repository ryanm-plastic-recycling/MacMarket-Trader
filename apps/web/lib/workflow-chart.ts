import type { IndicatorLegendEntry, IndicatorPane } from "@/lib/chart-indicators";
import { INDICATOR_REGISTRY, type IndicatorId } from "@/lib/indicator-framework";
import type { Time } from "lightweight-charts";

export type WorkflowIndicatorPresetId = "clean" | "trend" | "momentum" | "volatility" | "all" | "custom";
export type WorkflowPanelState = {
  showVolume: boolean;
  showMomentum: boolean;
};
export type WorkflowHoverLegendValue = {
  label: string;
  pane: IndicatorPane;
  color: string;
  value: number | null;
};

export type WorkflowIndicatorPreset = {
  id: Exclude<WorkflowIndicatorPresetId, "custom">;
  label: string;
  description: string;
  indicators: IndicatorId[];
};

export function formatChartTimestamp(raw: Time | number | null | undefined): string {
  if (!raw) return "Unavailable";
  if (typeof raw === "number") {
    return new Date(raw * 1000).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }
  if (typeof raw !== "string") {
    return `${raw.year}-${String(raw.month).padStart(2, "0")}-${String(raw.day).padStart(2, "0")}`;
  }
  const timestamp = new Date(raw);
  if (Number.isNaN(timestamp.getTime())) return raw;
  return timestamp.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export const WORKFLOW_INDICATOR_PRESETS: WorkflowIndicatorPreset[] = [
  { id: "clean", label: "Clean", description: "Price + volume only", indicators: ["volume"] },
  { id: "trend", label: "Trend", description: "Price + SMA 20 + SMA 50", indicators: ["sma20", "sma50"] },
  { id: "momentum", label: "Momentum", description: "Price + volume + RSI 14", indicators: ["volume", "rsi"] },
  { id: "volatility", label: "Volatility", description: "Price + Bollinger", indicators: ["bollinger"] },
  {
    id: "all",
    label: "All",
    description: "Manual review with every supported indicator",
    indicators: ["volume", "sma20", "sma50", "ema20", "ema50", "ema200", "vwap", "bollinger", "prior_day_levels", "rsi"],
  },
];

const VALID_INDICATORS = new Set(INDICATOR_REGISTRY.map((item) => item.id));

function uniqueIndicators(indicators: IndicatorId[]): IndicatorId[] {
  return Array.from(new Set(indicators));
}

export function getWorkflowPresetIndicators(
  presetId: Exclude<WorkflowIndicatorPresetId, "custom">,
  supportedIds: IndicatorId[],
): IndicatorId[] {
  const supportedSet = new Set(supportedIds);
  const preset = WORKFLOW_INDICATOR_PRESETS.find((item) => item.id === presetId);
  if (!preset) return [];
  return preset.indicators.filter((item) => supportedSet.has(item));
}

export function sanitizeWorkflowIndicatorSelection(
  input: string[] | null | undefined,
  supportedIds: IndicatorId[],
): { selected: IndicatorId[]; unsupported: IndicatorId[] } {
  const supportedSet = new Set(supportedIds);
  const normalized = uniqueIndicators((input ?? []).filter((item): item is IndicatorId => VALID_INDICATORS.has(item as IndicatorId)));
  const selected = normalized.filter((item) => supportedSet.has(item));
  const unsupported = normalized.filter((item) => !supportedSet.has(item));
  if (selected.length > 0) return { selected, unsupported };
  return {
    selected: getWorkflowPresetIndicators("trend", supportedIds),
    unsupported,
  };
}

export function detectWorkflowIndicatorPreset(
  selectedIndicators: IndicatorId[],
  supportedIds: IndicatorId[],
): WorkflowIndicatorPresetId {
  const selected = uniqueIndicators(selectedIndicators.filter((item) => supportedIds.includes(item))).sort();
  for (const preset of WORKFLOW_INDICATOR_PRESETS) {
    const presetIndicators = getWorkflowPresetIndicators(preset.id, supportedIds).sort();
    if (presetIndicators.length === selected.length && presetIndicators.every((item, idx) => item === selected[idx])) {
      return preset.id;
    }
  }
  return "custom";
}

export function getWorkflowPanelState(selectedIndicators: IndicatorId[]): WorkflowPanelState {
  return {
    showVolume: selectedIndicators.includes("volume"),
    showMomentum: selectedIndicators.includes("rsi"),
  };
}

export function extractWorkflowHoverLegendValues(
  legendEntries: IndicatorLegendEntry[],
  activeTimeKey: string | null,
): WorkflowHoverLegendValue[] {
  return legendEntries.map((entry) => ({
    label: entry.label,
    pane: entry.pane,
    color: entry.color,
    value: activeTimeKey ? entry.valuesByTime.get(activeTimeKey) ?? null : null,
  }));
}
