import { describe, expect, it } from "vitest";
import {
  buildIndicatorProvenance,
  formatIndicatorKey,
  formatIndicatorValue,
  indicatorTone,
  strategyFitText,
} from "./analyze-helpers";

describe("formatIndicatorKey", () => {
  it("returns human label for known keys", () => {
    expect(formatIndicatorKey("ema20_vs_price")).toBe("EMA20 vs price");
    expect(formatIndicatorKey("rsi")).toBe("RSI");
    expect(formatIndicatorKey("macd")).toBe("MACD");
    expect(formatIndicatorKey("atr")).toBe("ATR");
    expect(formatIndicatorKey("relative_volume")).toBe("RVOL");
  });

  it("capitalises unknown snake_case keys", () => {
    expect(formatIndicatorKey("some_unknown_key")).toBe("Some Unknown Key");
  });
});

describe("indicatorTone", () => {
  it("ema20_vs_price: above → good, below → warn", () => {
    expect(indicatorTone("ema20_vs_price", "above")).toBe("good");
    expect(indicatorTone("ema20_vs_price", "below")).toBe("warn");
  });

  it("rsi: overbought / oversold → warn, midrange → neutral", () => {
    expect(indicatorTone("rsi", 72)).toBe("warn");
    expect(indicatorTone("rsi", 28)).toBe("warn");
    expect(indicatorTone("rsi", 50)).toBe("neutral");
    expect(indicatorTone("rsi", 70)).toBe("warn");
    expect(indicatorTone("rsi", 30)).toBe("warn");
  });

  it("relative_volume: ≥1.3 → good, <0.8 → warn, otherwise neutral", () => {
    expect(indicatorTone("relative_volume", 1.5)).toBe("good");
    expect(indicatorTone("relative_volume", 1.3)).toBe("good");
    expect(indicatorTone("relative_volume", 0.7)).toBe("warn");
    expect(indicatorTone("relative_volume", 1.0)).toBe("neutral");
  });

  it("macd: positive → good, negative → warn, zero → neutral", () => {
    expect(indicatorTone("macd", 0.5)).toBe("good");
    expect(indicatorTone("macd", -0.1)).toBe("warn");
    expect(indicatorTone("macd", 0)).toBe("neutral");
  });

  it("unknown key → neutral", () => {
    expect(indicatorTone("mystery_key", 99)).toBe("neutral");
  });
});

describe("formatIndicatorValue", () => {
  it("ema20_vs_price: above annotates as bullish", () => {
    expect(formatIndicatorValue("ema20_vs_price", "above")).toContain("bullish");
  });

  it("ema20_vs_price: below annotates as bearish", () => {
    expect(formatIndicatorValue("ema20_vs_price", "below")).toContain("bearish");
  });

  it("rsi: formats with label", () => {
    expect(formatIndicatorValue("rsi", 75)).toContain("overbought");
    expect(formatIndicatorValue("rsi", 25)).toContain("oversold");
    expect(formatIndicatorValue("rsi", 50)).toContain("neutral");
  });

  it("relative_volume: formats with label", () => {
    expect(formatIndicatorValue("relative_volume", 1.5)).toContain("elevated");
    expect(formatIndicatorValue("relative_volume", 1.0)).toContain("average");
    expect(formatIndicatorValue("relative_volume", 0.5)).toContain("thin");
  });

  it("macd: formats with sign label", () => {
    expect(formatIndicatorValue("macd", 0.25)).toContain("positive");
    expect(formatIndicatorValue("macd", -0.1)).toContain("negative");
    expect(formatIndicatorValue("macd", 0)).toContain("flat");
  });

  it("atr: appends daily range estimate", () => {
    expect(formatIndicatorValue("atr", 1.23)).toContain("daily range estimate");
  });

  it("unknown key: returns string representation", () => {
    expect(formatIndicatorValue("unknown", 42)).toBe("42");
  });
});

describe("buildIndicatorProvenance", () => {
  it("maps snapshot to labeled tone-annotated items", () => {
    const items = buildIndicatorProvenance({ ema20_vs_price: "above", rsi: 55 });
    expect(items).toHaveLength(2);
    expect(items[0].key).toBe("ema20_vs_price");
    expect(items[0].label).toBe("EMA20 vs price");
    expect(items[0].tone).toBe("good");
    expect(items[1].tone).toBe("neutral");
  });

  it("returns empty array for empty snapshot", () => {
    expect(buildIndicatorProvenance({})).toEqual([]);
  });
});

describe("strategyFitText", () => {
  it("produces · separated summary for strong scores", () => {
    const text = strategyFitText({
      strategy_fit_score: 0.8,
      regime_fit_score: 0.7,
      liquidity_score: 0.7,
      volatility_suitability_score: 0.7,
    });
    expect(text).toContain("strategy fit: strong");
    expect(text).toContain("regime: aligned");
    expect(text).toContain("liquidity: adequate");
    expect(text).toContain("volatility: suitable");
    expect(text).toContain(" · ");
  });

  it("uses weak/misaligned/thin labels for low scores", () => {
    const text = strategyFitText({
      strategy_fit_score: 0.2,
      regime_fit_score: 0.2,
    });
    expect(text).toContain("strategy fit: weak");
    expect(text).toContain("regime: misaligned");
  });

  it("omits keys that are missing from breakdown", () => {
    const text = strategyFitText({ strategy_fit_score: 0.8 });
    expect(text).toBe("strategy fit: strong");
  });

  it("returns empty string for empty breakdown", () => {
    expect(strategyFitText({})).toBe("");
  });
});
