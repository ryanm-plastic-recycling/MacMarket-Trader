import { describe, expect, it } from "vitest";

import { applyIndicatorsToChart, buildWorkflowIndicatorModel, FIRST_CLASS_WORKFLOW_INDICATORS, HACO_CONTEXT_SUPPORTED_INDICATORS } from "@/lib/chart-indicators";
import type { IndicatorId } from "@/lib/indicator-framework";

type SeriesRecorder = { kind: string; options?: Record<string, unknown>; data: unknown[] };

function buildChartRecorder() {
  const series: SeriesRecorder[] = [];
  const scaleCalls: Array<{ id: string; options: Record<string, unknown> }> = [];
  return {
    series,
    scaleCalls,
    chart: {
      addLineSeries: (options?: Record<string, unknown>) => {
        const record: SeriesRecorder = { kind: "line", options, data: [] };
        series.push(record);
        return { setData: (data: unknown[]) => { record.data = data; } };
      },
      addHistogramSeries: (options?: Record<string, unknown>) => {
        const record: SeriesRecorder = { kind: "histogram", options, data: [] };
        series.push(record);
        return { setData: (data: unknown[]) => { record.data = data; } };
      },
      priceScale: (id: string) => ({
        applyOptions: (options: Record<string, unknown>) => { scaleCalls.push({ id, options }); },
      }),
    },
  };
}

const candles = Array.from({ length: 240 }).map((_, idx) => ({
  time: `2026-01-${String((idx % 28) + 1).padStart(2, "0")}` as unknown as number,
  open: 100 + idx * 0.25,
  high: 101 + idx * 0.25,
  low: 99 + idx * 0.25,
  close: 100 + idx * 0.3,
  volume: 1_000_000 + idx * 1_000,
}));

describe("applyIndicatorsToChart", () => {
  it("keeps HACO context indicator contract restricted to rendered strips", () => {
    expect(HACO_CONTEXT_SUPPORTED_INDICATORS).toEqual(["haco", "hacolt"]);
    expect(HACO_CONTEXT_SUPPORTED_INDICATORS.every((item) => !FIRST_CLASS_WORKFLOW_INDICATORS.includes(item))).toBe(true);
  });

  it("renders first-class workflow indicators with data-bearing series", () => {
    const { chart, series, scaleCalls } = buildChartRecorder();
    const selected: IndicatorId[] = ["volume", "sma20", "sma50", "ema20", "ema50", "ema200", "vwap", "bollinger", "prior_day_levels", "rsi"];
    const result = applyIndicatorsToChart(chart as never, candles as never, selected);

    expect(series.length).toBeGreaterThanOrEqual(13);
    expect(series.some((entry) => entry.kind === "histogram" && entry.data.length === candles.length)).toBe(true);
    expect(series.some((entry) => entry.options?.priceScaleId === "rsi" && entry.data.length > 0)).toBe(true);
    expect(scaleCalls.some((call) => call.id === "volume")).toBe(true);
    expect(scaleCalls.some((call) => call.id === "rsi")).toBe(true);
    expect(result.legendEntries.some((entry) => entry.label === "SMA 20" && entry.latestValue != null)).toBe(true);
    expect(result.legendEntries.some((entry) => entry.label === "RSI 14" && entry.pane === "momentum")).toBe(true);
  });

  it("builds separate panel descriptors for price, volume, and momentum studies", () => {
    const model = buildWorkflowIndicatorModel(candles as never, ["volume", "sma20", "bollinger", "rsi"]);
    expect(model.priceOverlays.some((entry) => entry.label === "SMA 20")).toBe(true);
    expect(model.volumePanel?.label).toBe("Volume");
    expect(model.momentumPanels[0]?.label).toBe("RSI 14");
    expect(model.momentumPanels[0]?.guides?.map((entry) => entry.value)).toEqual([70, 30]);
  });
});
