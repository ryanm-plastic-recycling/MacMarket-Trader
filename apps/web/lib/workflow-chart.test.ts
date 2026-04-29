import { describe, expect, it } from "vitest";

import {
  detectWorkflowIndicatorPreset,
  extractWorkflowHoverLegendValues,
  getWorkflowPresetIndicators,
  getWorkflowPanelState,
  sanitizeWorkflowIndicatorSelection,
} from "@/lib/workflow-chart";
import type { IndicatorLegendEntry } from "@/lib/chart-indicators";
import type { IndicatorId } from "@/lib/indicator-framework";

const supportedIndicators: IndicatorId[] = ["volume", "sma20", "sma50", "ema20", "ema50", "ema200", "vwap", "bollinger", "prior_day_levels", "rsi"];

describe("workflow chart presets", () => {
  it("defaults workflow charts to the trend preset when no stored selection exists", () => {
    const result = sanitizeWorkflowIndicatorSelection([], supportedIndicators);
    expect(result.selected).toEqual(["sma20", "sma50"]);
    expect(result.unsupported).toEqual([]);
  });

  it("preserves known but unsupported indicators for operator visibility", () => {
    const result = sanitizeWorkflowIndicatorSelection(["haco", "rsi"], supportedIndicators);
    expect(result.selected).toEqual(["rsi"]);
    expect(result.unsupported).toEqual(["haco"]);
  });

  it("detects exact preset matches and falls back to custom otherwise", () => {
    expect(detectWorkflowIndicatorPreset(["volume"], supportedIndicators)).toBe("clean");
    expect(detectWorkflowIndicatorPreset(["volume", "rsi"], supportedIndicators)).toBe("momentum");
    expect(detectWorkflowIndicatorPreset(["ema20", "volume"], supportedIndicators)).toBe("custom");
  });

  it("filters preset indicators to only those supported by the current chart", () => {
    expect(getWorkflowPresetIndicators("all", ["volume", "sma20", "rsi"])).toEqual(["volume", "sma20", "rsi"]);
  });

  it("splits volume and momentum indicators into dedicated lower panels", () => {
    expect(getWorkflowPanelState(["sma20", "volume", "rsi"])).toEqual({ showVolume: true, showMomentum: true });
    expect(getWorkflowPanelState(["sma20", "sma50"])).toEqual({ showVolume: false, showMomentum: false });
  });

  it("extracts synchronized hover values and preserves missing points as null", () => {
    const legendEntries: IndicatorLegendEntry[] = [
      { id: "sma20", label: "SMA 20", color: "#fff", pane: "price", latestValue: 123, valuesByTime: new Map([["t1", 123]]) },
      { id: "rsi", label: "RSI 14", color: "#aaa", pane: "momentum", latestValue: 55, valuesByTime: new Map() },
    ];
    expect(extractWorkflowHoverLegendValues(legendEntries, "t1")).toEqual([
      { label: "SMA 20", pane: "price", color: "#fff", value: 123 },
      { label: "RSI 14", pane: "momentum", color: "#aaa", value: null },
    ]);
  });
});
