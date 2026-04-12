"use client";

import { createChart, type CandlestickData, ColorType, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, ErrorState, StatusBadge } from "@/components/operator-ui";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS, HACO_CONTEXT_SUPPORTED_INDICATORS } from "@/lib/chart-indicators";
import { fetchHacoChart, type HacoChartPayload } from "@/lib/haco-api";

const STORAGE_KEY = "macmarket-indicators-haco";
const HACO_WORKSPACE_SUPPORTED_INDICATORS: IndicatorId[] = [...FIRST_CLASS_WORKFLOW_INDICATORS, ...HACO_CONTEXT_SUPPORTED_INDICATORS];

export function HacoWorkspace({ embedded = false }: { embedded?: boolean }) {
  const [symbol, setSymbol] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("1D");
  const [data, setData] = useState<HacoChartPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const priceRef = useRef<HTMLDivElement | null>(null);
  const hacoRef = useRef<HTMLDivElement | null>(null);
  const hacoltRef = useRef<HTMLDivElement | null>(null);
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchHacoChart({ symbol, timeframe, include_heikin_ashi: true });
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load HACO workspace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      try {
        setSelectedIndicators(
          normalizeSelection(raw ? (JSON.parse(raw) as string[]) : HACO_WORKSPACE_SUPPORTED_INDICATORS).filter((id) =>
            HACO_WORKSPACE_SUPPORTED_INDICATORS.includes(id),
          ),
        );
      } catch {
        setSelectedIndicators(HACO_WORKSPACE_SUPPORTED_INDICATORS);
      }
    }
    void load();
  }, []);

  function onIndicatorChange(next: IndicatorId[]) {
    const normalized = normalizeSelection(next).filter((id) => HACO_WORKSPACE_SUPPORTED_INDICATORS.includes(id));
    setSelectedIndicators(normalized);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  }

  useEffect(() => {
    if (!priceRef.current || !hacoRef.current || !hacoltRef.current || !data) return;

    const baseOptions = {
      layout: { background: { type: ColorType.Solid, color: "#0b1219" }, textColor: "#d9e2ef" },
      grid: { vertLines: { color: "#1f2a36" }, horzLines: { color: "#1f2a36" } },
      rightPriceScale: { borderColor: "#26303a" },
      timeScale: { borderColor: "#26303a" },
      autoSize: true,
    };

    const priceChart = createChart(priceRef.current, { ...baseOptions, height: embedded ? 260 : 330 });
    const hacoChart = createChart(hacoRef.current, { ...baseOptions, height: 110 });
    const hacoltChart = createChart(hacoltRef.current, { ...baseOptions, height: 110 });

    const candles: CandlestickData<Time>[] = data.candles.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close }));
    const priceSeries: ISeriesApi<"Candlestick"> = priceChart.addCandlestickSeries();
    priceSeries.setData(candles);
    applyIndicatorsToChart(priceChart, data.candles.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume })), selectedIndicators);
    priceSeries.setMarkers(data.markers.map((m) => ({
      time: m.time as Time,
      position: m.direction === "buy" ? "belowBar" : "aboveBar",
      color: m.direction === "buy" ? "#21c06e" : "#d14b4b",
      shape: m.direction === "buy" ? "arrowUp" : "arrowDown",
      text: m.text,
    })));
    priceChart.timeScale().fitContent();

    if (selectedIndicators.includes("haco")) {
      const hacoSeries = hacoChart.addHistogramSeries({ base: 0, color: "#21c06e" });
      hacoSeries.setData(data.haco_strip.map((p) => ({ time: p.time as Time, value: p.value, color: p.state === "green" ? "#21c06e" : "#c64242" })));
    }

    if (selectedIndicators.includes("hacolt")) {
      const hacoltSeries = hacoltChart.addHistogramSeries({ base: 0, color: "#4d8dff" });
      hacoltSeries.setData(data.hacolt_strip.map((p) => ({ time: p.time as Time, value: p.value, color: p.direction === "up" ? "#4d8dff" : "#7a4dc1" })));
    }

    let syncing = false;
    const syncFrom = (source: IChartApi, targets: IChartApi[]) => {
      source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || syncing) return;
        syncing = true;
        targets.forEach((target) => target.timeScale().setVisibleLogicalRange(range));
        syncing = false;
      });
    };
    syncFrom(priceChart, [hacoChart, hacoltChart]);
    syncFrom(hacoChart, [priceChart, hacoltChart]);
    syncFrom(hacoltChart, [priceChart, hacoChart]);

    return () => {
      priceChart.remove();
      hacoChart.remove();
      hacoltChart.remove();
    };
  }, [data, embedded, selectedIndicators]);

  const summary = useMemo(() => data?.explanation, [data]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {!embedded ? <Card>
        <h2 style={{ margin: 0 }}>HACO operator workspace</h2>
        <p style={{ marginBottom: 0, color: "#9fb0c3" }}>
          Source: <StatusBadge tone={data?.fallback_mode ? "warn" : "good"}>{data?.data_source ?? "not loaded"}</StatusBadge> · shared canonical time index active.
        </p>
      </Card> : null}

      <div className="op-row">
        <label>Symbol <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={{ marginLeft: 8 }} /></label>
        <label>Timeframe <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} style={{ marginLeft: 8 }}><option value="1D">1D</option><option value="4H">4H</option><option value="1H">1H</option></select></label>
        <button onClick={() => void load()} disabled={loading}>{loading ? "Loading..." : "Run HACO analysis"}</button>
      </div>

      {error ? <ErrorState title="HACO unavailable" hint={error} /> : null}

      <Card title={embedded ? "HACO mini-module" : "Price pane + synced HACO/HACOLT strips"}>
        <IndicatorSelector selected={selectedIndicators} onChange={onIndicatorChange} enabledIds={HACO_WORKSPACE_SUPPORTED_INDICATORS} />
        <p style={{ margin: "6px 0", color: "#9fb0c3" }}>
          Price pane overlays and synced HACO/HACOLT strips share one canonical time axis.
        </p>
        <div ref={priceRef} />
        <div ref={hacoRef} style={{ marginTop: 6 }} />
        <div ref={hacoltRef} style={{ marginTop: 6 }} />
      </Card>

      <Card title="Signal summary">
        <div style={{ display: "grid", gap: 6 }}>
          {/* HACO state */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", minWidth: 130 }}>HACO state</span>
            <span style={{
              fontWeight: 600,
              color: summary?.current_haco_state === "green" ? "#21c06e" : summary?.current_haco_state === "red" ? "#c64242" : "#9fb0c3",
            }}>
              {summary?.current_haco_state ?? "—"}
            </span>
          </div>
          {/* HACOLT direction */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", minWidth: 130 }}>HACOLT direction</span>
            <span style={{
              fontWeight: 600,
              color: summary?.current_hacolt_direction === "up" ? "#4d8dff" : summary?.current_hacolt_direction === "down" ? "#7a4dc1" : "#9fb0c3",
            }}>
              {summary?.current_hacolt_direction ?? "—"}
            </span>
          </div>
          {/* Latest flip */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", minWidth: 130 }}>Latest flip</span>
            <span>{summary?.latest_flip ?? "—"}</span>
            {summary?.latest_flip_bars_ago != null ? (
              <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>({summary.latest_flip_bars_ago} bar{summary.latest_flip_bars_ago === 1 ? "" : "s"} ago)</span>
            ) : null}
          </div>

          {/* Alignment narrative */}
          {summary ? (() => {
            const state = summary.current_haco_state as string | undefined;
            const lt = summary.current_hacolt_direction as string | undefined;
            const barsAgo = summary.latest_flip_bars_ago as number | undefined;
            const aligned = state === "green" && lt === "up";
            const diverged = (state === "green" && lt === "down") || (state === "red" && lt === "up");
            const stale = barsAgo != null && barsAgo > 5;
            let narrative = "";
            let narrativeColor = "#9fb0c3";
            if (aligned) {
              narrative = stale
                ? `HACO is green and HACOLT is trending up — aligned bullish — but the last flip was ${String(barsAgo)} bars ago. Confirm momentum is still active before entering.`
                : `HACO is green and HACOLT is trending up. Momentum and long-term trend are aligned. Favorable context for long continuation setups.`;
              narrativeColor = "#21c06e";
            } else if (diverged) {
              narrative = state === "green"
                ? `HACO recently flipped green but HACOLT is still trending down. Short-term momentum is bullish but the long-term trend context is not supportive — treat as a counter-trend signal; tighter stops.`
                : `HACO is red but HACOLT is trending up. Short-term momentum is bearish inside an uptrend — may be a pullback opportunity rather than a reversal. Wait for HACO green before acting.`;
              narrativeColor = "#f2a03f";
            } else if (state === "red" && lt === "down") {
              narrative = stale
                ? `HACO is red and HACOLT is trending down — aligned bearish — but the last flip was ${String(barsAgo)} bars ago. Bearish context may be extended; confirm before adding short exposure.`
                : `HACO is red and HACOLT is trending down. Both short-term momentum and long-term trend are bearish. Avoid long setups; this context favors no-trade or short candidates.`;
              narrativeColor = "#c64242";
            } else {
              narrative = "Insufficient data to determine alignment narrative.";
            }
            return (
              <div style={{ marginTop: 4, paddingTop: 8, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
                <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)", marginBottom: 4 }}>ALIGNMENT</div>
                <p style={{ margin: 0, fontSize: "0.85rem", lineHeight: 1.5, color: narrativeColor }}>{narrative}</p>
              </div>
            );
          })() : null}
        </div>
      </Card>
    </div>
  );
}
