import { describe, expect, it } from "vitest";

import { applyIndicatorsToChart } from "@/lib/chart-indicators";
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
  it("renders first-class workflow indicators with data-bearing series", () => {
    const { chart, series, scaleCalls } = buildChartRecorder();
    const selected: IndicatorId[] = ["ema20", "ema50", "ema200", "vwap", "bollinger", "prior_day_levels", "volume", "rsi"];
    applyIndicatorsToChart(chart as never, candles as never, selected);

    expect(series.length).toBeGreaterThanOrEqual(11);
    expect(series.some((entry) => entry.kind === "histogram" && entry.data.length === candles.length)).toBe(true);
    expect(series.some((entry) => entry.options?.priceScaleId === "rsi" && entry.data.length > 0)).toBe(true);
    expect(scaleCalls.some((call) => call.id === "volume")).toBe(true);
    expect(scaleCalls.some((call) => call.id === "rsi")).toBe(true);
  });
});
