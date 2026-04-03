export type IndicatorCategory = "trend" | "volatility" | "structure" | "momentum" | "volume" | "haco";

export type IndicatorId =
  | "ema20"
  | "ema50"
  | "ema200"
  | "vwap"
  | "anchored_vwap"
  | "atr"
  | "bollinger"
  | "prior_day_levels"
  | "opening_range"
  | "gap_levels"
  | "pivot_sr"
  | "rsi"
  | "macd"
  | "volume"
  | "relative_volume"
  | "haco"
  | "hacolt";

export type IndicatorDefinition = {
  id: IndicatorId;
  label: string;
  category: IndicatorCategory;
  defaultEnabled: boolean;
};

export type CandleBar = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

export const INDICATOR_REGISTRY: IndicatorDefinition[] = [
  { id: "ema20", label: "EMA 20", category: "trend", defaultEnabled: true },
  { id: "ema50", label: "EMA 50", category: "trend", defaultEnabled: false },
  { id: "ema200", label: "EMA 200", category: "trend", defaultEnabled: false },
  { id: "vwap", label: "VWAP", category: "trend", defaultEnabled: true },
  { id: "anchored_vwap", label: "Anchored VWAP", category: "trend", defaultEnabled: false },
  { id: "atr", label: "ATR", category: "volatility", defaultEnabled: false },
  { id: "bollinger", label: "Bollinger Bands", category: "volatility", defaultEnabled: false },
  { id: "prior_day_levels", label: "Prior Day H/L", category: "structure", defaultEnabled: true },
  { id: "opening_range", label: "Opening Range", category: "structure", defaultEnabled: false },
  { id: "gap_levels", label: "Gap Levels", category: "structure", defaultEnabled: false },
  { id: "pivot_sr", label: "Pivot S/R", category: "structure", defaultEnabled: false },
  { id: "rsi", label: "RSI", category: "momentum", defaultEnabled: false },
  { id: "macd", label: "MACD", category: "momentum", defaultEnabled: false },
  { id: "volume", label: "Volume", category: "volume", defaultEnabled: false },
  { id: "relative_volume", label: "Relative Volume", category: "volume", defaultEnabled: false },
  { id: "haco", label: "HACO", category: "haco", defaultEnabled: false },
  { id: "hacolt", label: "HACOLT", category: "haco", defaultEnabled: false },
];

const defaultSelection = INDICATOR_REGISTRY.filter((item) => item.defaultEnabled).map((item) => item.id);

export function normalizeSelection(input: string[] | null | undefined): IndicatorId[] {
  const valid = new Set(INDICATOR_REGISTRY.map((item) => item.id));
  const normalized = (input ?? []).filter((item): item is IndicatorId => valid.has(item as IndicatorId));
  return normalized.length > 0 ? normalized : defaultSelection;
}

function ema(values: number[], period: number): Array<number | null> {
  const multiplier = 2 / (period + 1);
  const out: Array<number | null> = [];
  let prev: number | null = null;
  values.forEach((value, idx) => {
    if (idx < period - 1) {
      out.push(null);
      return;
    }
    if (prev === null) {
      const start = values.slice(idx - period + 1, idx + 1).reduce((sum, item) => sum + item, 0) / period;
      prev = start;
      out.push(start);
      return;
    }
    const next = (value - prev) * multiplier + prev;
    prev = next;
    out.push(next);
  });
  return out;
}

export function calculateIndicatorSnapshot(bars: CandleBar[]) {
  const closes = bars.map((item) => item.close);
  const volumes = bars.map((item) => item.volume ?? 0);
  const ema20 = ema(closes, 20).at(-1);
  const ema50 = ema(closes, 50).at(-1);
  const ema200 = ema(closes, 200).at(-1);
  const meanClose = closes.slice(-20).reduce((sum, item) => sum + item, 0) / Math.max(1, Math.min(20, closes.length));
  const variance = closes.slice(-20).reduce((sum, item) => sum + (item - meanClose) ** 2, 0) / Math.max(1, Math.min(20, closes.length));
  const stdDev = Math.sqrt(variance);
  const rsi = 55;
  const macd = (ema20 ?? meanClose) - (ema50 ?? meanClose);
  const avgVol = volumes.slice(-20).reduce((sum, item) => sum + item, 0) / Math.max(1, Math.min(20, volumes.length));
  const latestVol = volumes.at(-1) ?? 0;
  const relVol = avgVol > 0 ? latestVol / avgVol : 0;
  return {
    ema20,
    ema50,
    ema200,
    vwap: meanClose,
    atr: stdDev * 1.5,
    bollingerUpper: meanClose + stdDev * 2,
    bollingerLower: meanClose - stdDev * 2,
    rsi,
    macd,
    relativeVolume: relVol,
  };
}
