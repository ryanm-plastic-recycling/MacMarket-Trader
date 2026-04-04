import type { CandlestickData, HistogramData, IChartApi, Time } from "lightweight-charts";

import type { IndicatorId } from "@/lib/indicator-framework";

type NumericPoint = { time: Time; value: number };

export const FIRST_CLASS_WORKFLOW_INDICATORS: IndicatorId[] = [
  "ema20",
  "ema50",
  "ema200",
  "vwap",
  "bollinger",
  "prior_day_levels",
  "volume",
  "rsi",
];

export const HACO_CONTEXT_SUPPORTED_INDICATORS: IndicatorId[] = ["haco", "hacolt"];

function ema(values: number[], period: number): Array<number | null> {
  const multiplier = 2 / (period + 1);
  const output: Array<number | null> = [];
  let prev: number | null = null;
  values.forEach((value, idx) => {
    if (idx < period - 1) {
      output.push(null);
      return;
    }
    if (prev === null) {
      const seed = values.slice(idx - period + 1, idx + 1).reduce((acc, item) => acc + item, 0) / period;
      prev = seed;
      output.push(seed);
      return;
    }
    const next = (value - prev) * multiplier + prev;
    prev = next;
    output.push(next);
  });
  return output;
}

function buildSeries(times: Time[], values: Array<number | null>): NumericPoint[] {
  return values
    .map((value, idx) => (value == null ? null : ({ time: times[idx], value })))
    .filter((item): item is NumericPoint => item !== null);
}

function calculateVwap(closes: number[], highs: number[], lows: number[], volumes: number[]): Array<number | null> {
  let cumulativeTpv = 0;
  let cumulativeVolume = 0;
  return closes.map((close, idx) => {
    const volume = volumes[idx] ?? 0;
    const typicalPrice = ((highs[idx] ?? close) + (lows[idx] ?? close) + close) / 3;
    cumulativeTpv += typicalPrice * volume;
    cumulativeVolume += volume;
    if (cumulativeVolume <= 0) return null;
    return cumulativeTpv / cumulativeVolume;
  });
}

function calculateBollinger(closes: number[], period = 20) {
  const mid: Array<number | null> = [];
  const upper: Array<number | null> = [];
  const lower: Array<number | null> = [];
  closes.forEach((_, idx) => {
    if (idx < period - 1) {
      mid.push(null);
      upper.push(null);
      lower.push(null);
      return;
    }
    const slice = closes.slice(idx - period + 1, idx + 1);
    const mean = slice.reduce((acc, item) => acc + item, 0) / period;
    const variance = slice.reduce((acc, item) => acc + (item - mean) ** 2, 0) / period;
    const sigma = Math.sqrt(variance);
    mid.push(mean);
    upper.push(mean + 2 * sigma);
    lower.push(mean - 2 * sigma);
  });
  return { mid, upper, lower };
}

function calculateRsi(closes: number[], period = 14): Array<number | null> {
  if (closes.length === 0) return [];
  const gains: number[] = [0];
  const losses: number[] = [0];
  for (let idx = 1; idx < closes.length; idx += 1) {
    const delta = closes[idx] - closes[idx - 1];
    gains.push(Math.max(delta, 0));
    losses.push(Math.max(-delta, 0));
  }
  let avgGain = 0;
  let avgLoss = 0;
  const out: Array<number | null> = closes.map(() => null);
  for (let idx = 1; idx < closes.length; idx += 1) {
    if (idx <= period) {
      avgGain += gains[idx];
      avgLoss += losses[idx];
      if (idx === period) {
        avgGain /= period;
        avgLoss /= period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        out[idx] = 100 - 100 / (1 + rs);
      }
      continue;
    }
    avgGain = (avgGain * (period - 1) + gains[idx]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[idx]) / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    out[idx] = 100 - 100 / (1 + rs);
  }
  return out;
}

export function applyIndicatorsToChart(
  chart: IChartApi,
  candles: CandlestickData<Time>[],
  selectedIndicators: IndicatorId[],
): void {
  const times = candles.map((item) => item.time);
  const opens = candles.map((item) => Number(item.open));
  const highs = candles.map((item) => Number(item.high));
  const lows = candles.map((item) => Number(item.low));
  const closes = candles.map((item) => Number(item.close));

  if (selectedIndicators.includes("volume")) {
    const volumes = chart.addHistogramSeries({
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      color: "#54708b",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.72, bottom: 0 } });
    const data: HistogramData<Time>[] = candles.map((item, idx) => ({
      time: item.time,
      value: Number((item as { volume?: number }).volume ?? 0),
      color: closes[idx] >= opens[idx] ? "#2c9f5d" : "#b24f4f",
    }));
    volumes.setData(data);
  }

  if (selectedIndicators.includes("ema20")) {
    chart.addLineSeries({ color: "#5ab0ff", lineWidth: 2 }).setData(buildSeries(times, ema(closes, 20)));
  }
  if (selectedIndicators.includes("ema50")) {
    chart.addLineSeries({ color: "#9d7dff", lineWidth: 2 }).setData(buildSeries(times, ema(closes, 50)));
  }
  if (selectedIndicators.includes("ema200")) {
    chart.addLineSeries({ color: "#f2c96d", lineWidth: 2 }).setData(buildSeries(times, ema(closes, 200)));
  }

  if (selectedIndicators.includes("vwap")) {
    const volumes = candles.map((item) => Number((item as { volume?: number }).volume ?? 0));
    chart.addLineSeries({ color: "#4dd0c6", lineWidth: 2 }).setData(buildSeries(times, calculateVwap(closes, highs, lows, volumes)));
  }

  if (selectedIndicators.includes("bollinger")) {
    const bands = calculateBollinger(closes, 20);
    chart.addLineSeries({ color: "#7eb6ff", lineWidth: 1, lineStyle: 2 }).setData(buildSeries(times, bands.upper));
    chart.addLineSeries({ color: "#6f7786", lineWidth: 1, lineStyle: 2 }).setData(buildSeries(times, bands.mid));
    chart.addLineSeries({ color: "#7eb6ff", lineWidth: 1, lineStyle: 2 }).setData(buildSeries(times, bands.lower));
  }

  if (selectedIndicators.includes("prior_day_levels") && candles.length > 1) {
    const prevHigh: Array<number | null> = [null];
    const prevLow: Array<number | null> = [null];
    for (let idx = 1; idx < candles.length; idx += 1) {
      prevHigh.push(highs[idx - 1]);
      prevLow.push(lows[idx - 1]);
    }
    chart.addLineSeries({ color: "#f29f67", lineWidth: 1, lineStyle: 1 }).setData(buildSeries(times, prevHigh));
    chart.addLineSeries({ color: "#f29f67", lineWidth: 1, lineStyle: 1 }).setData(buildSeries(times, prevLow));
  }

  if (selectedIndicators.includes("rsi")) {
    const rsiSeries = chart.addLineSeries({
      color: "#b9a0ff",
      lineWidth: 2,
      priceScaleId: "rsi",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("rsi").applyOptions({ scaleMargins: { top: 0.82, bottom: 0.05 }, autoScale: false });
    rsiSeries.setData(buildSeries(times, calculateRsi(closes)));
    chart.addLineSeries({ color: "#6b7080", lineWidth: 1, lineStyle: 1, priceScaleId: "rsi", lastValueVisible: false, priceLineVisible: false })
      .setData(times.map((time) => ({ time, value: 70 })));
    chart.addLineSeries({ color: "#6b7080", lineWidth: 1, lineStyle: 1, priceScaleId: "rsi", lastValueVisible: false, priceLineVisible: false })
      .setData(times.map((time) => ({ time, value: 30 })));
  }
}
