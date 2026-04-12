/**
 * Client-side helpers for the Symbol Analyze triage page.
 * Pure functions — no React imports, no side effects, safe to unit-test.
 */

export type IndicatorProvenanceItem = {
  key: string;
  label: string;
  display: string;
  tone: "good" | "warn" | "neutral";
};

// Human-readable labels for known indicator keys
const KEY_LABELS: Record<string, string> = {
  ema20_vs_price: "EMA20 vs price",
  rsi: "RSI",
  macd: "MACD",
  atr: "ATR",
  relative_volume: "RVOL",
};

/** Convert a snake_case indicator key to a readable label. */
export function formatIndicatorKey(key: string): string {
  return (
    KEY_LABELS[key] ??
    key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
  );
}

/** Determine the display tone for a known indicator key + value pair. */
export function indicatorTone(
  key: string,
  value: string | number,
): "good" | "warn" | "neutral" {
  switch (key) {
    case "ema20_vs_price":
      return value === "above" ? "good" : "warn";
    case "rsi": {
      const n = Number(value);
      return n >= 70 || n <= 30 ? "warn" : "neutral";
    }
    case "relative_volume":
      return Number(value) >= 1.3 ? "good" : Number(value) < 0.8 ? "warn" : "neutral";
    case "macd":
      return Number(value) > 0 ? "good" : Number(value) < 0 ? "warn" : "neutral";
    default:
      return "neutral";
  }
}

/** Format an indicator value with contextual annotation. */
export function formatIndicatorValue(key: string, value: string | number): string {
  switch (key) {
    case "ema20_vs_price":
      return `${value} — ${value === "above" ? "bullish alignment" : "bearish alignment"}`;
    case "rsi": {
      const n = Number(value);
      const label = n >= 70 ? "overbought" : n <= 30 ? "oversold" : "neutral";
      return `${n.toFixed(0)} (${label})`;
    }
    case "relative_volume": {
      const n = Number(value);
      const label = n >= 1.3 ? "elevated" : n >= 0.8 ? "average" : "thin";
      return `${n.toFixed(1)}x (${label})`;
    }
    case "macd": {
      const n = Number(value);
      return `${n.toFixed(2)} (${n > 0 ? "positive" : n < 0 ? "negative" : "flat"})`;
    }
    case "atr":
      return `${Number(value).toFixed(2)} (daily range estimate)`;
    default:
      return String(value);
  }
}

/**
 * Convert the raw indicator_snapshot dict into labeled, tone-annotated items
 * suitable for operator display.
 */
export function buildIndicatorProvenance(
  snapshot: Record<string, string | number>,
): IndicatorProvenanceItem[] {
  return Object.entries(snapshot).map(([key, value]) => ({
    key,
    label: formatIndicatorKey(key),
    display: formatIndicatorValue(key, value),
    tone: indicatorTone(key, value),
  }));
}

/**
 * Convert a strategy score_breakdown dict into a 1-line provenance summary.
 * Example: "strategy fit: strong · regime: aligned · liquidity: adequate"
 */
export function strategyFitText(breakdown: Record<string, number>): string {
  const band = (
    score: number | undefined,
    high: string,
    mid: string,
    low: string,
  ): string => {
    if (score === undefined) return "";
    return score >= 0.65 ? high : score >= 0.45 ? mid : low;
  };

  const parts = [
    band(breakdown.strategy_fit_score, "strategy fit: strong", "strategy fit: moderate", "strategy fit: weak"),
    band(breakdown.regime_fit_score, "regime: aligned", "regime: partial", "regime: misaligned"),
    band(breakdown.liquidity_score, "liquidity: adequate", "liquidity: moderate", "liquidity: thin"),
    band(breakdown.volatility_suitability_score, "volatility: suitable", "volatility: acceptable", "volatility: unfavorable"),
  ].filter(Boolean);

  return parts.join(" · ");
}
