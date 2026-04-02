"use client";

import { createChart, type CandlestickData, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { fetchHacoChart, type HacoChartPayload } from "@/lib/haco-api";

export function HacoWorkspace({ embedded = false }: { embedded?: boolean }) {
  const [symbol, setSymbol] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("1D");
  const [data, setData] = useState<HacoChartPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement | null>(null);

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
    void load();
  }, []);

  useEffect(() => {
    if (!chartRef.current || !data) return;
    const chart: IChartApi = createChart(chartRef.current, { height: embedded ? 360 : 480, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" }, grid: { vertLines: { color: "#1f2a36" }, horzLines: { color: "#1f2a36" } } });
    const candleSeries: ISeriesApi<"Candlestick"> = chart.addCandlestickSeries();
    const candles: CandlestickData<Time>[] = data.candles.map((c) => ({ time: c.index as Time, open: c.open, high: c.high, low: c.low, close: c.close }));
    candleSeries.setData(candles);
    candleSeries.setMarkers(
      data.markers.map((m) => ({
        time: m.index as Time,
        position: m.direction === "buy" ? "belowBar" : "aboveBar",
        color: m.direction === "buy" ? "#21c06e" : "#d14b4b",
        shape: m.direction === "buy" ? "arrowUp" : "arrowDown",
        text: m.text,
      }))
    );

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [data, embedded]);

  const summary = useMemo(() => data?.explanation, [data]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {!embedded ? <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
        <h2 style={{ marginTop: 0 }}>HACO operator workspace</h2>
        <p style={{ marginBottom: 0, color: "#9fb0c3" }}>
          Data source: {data?.data_source ?? "not loaded"} {data?.fallback_mode ? "(deterministic fallback active)" : "(provider-backed)"}
        </p>
      </div> : null}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <label>
          Symbol
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={{ marginLeft: 8, background: "#0e151d", color: "#d9e2ef", border: "1px solid #2b3642", padding: "8px 10px" }} />
        </label>
        <label>
          Timeframe
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} style={{ marginLeft: 8, background: "#0e151d", color: "#d9e2ef", border: "1px solid #2b3642", padding: "8px 10px" }}>
            <option value="1D">1D</option><option value="4H">4H</option><option value="1H">1H</option>
          </select>
        </label>
        <button onClick={load} disabled={loading} style={{ background: "#2d6cdf", border: "none", color: "white", padding: "8px 12px" }}>{loading ? "Loading..." : "Run HACO analysis"}</button>
        <span style={{ color: "#9fb0c3" }}>Data source: {data?.data_source ?? "-"}</span>
      </div>

      {error ? <div style={{ color: "#ff8b8b" }}>{error}</div> : null}

      <div style={{ display: "grid", gridTemplateColumns: embedded ? "1fr" : "2fr 1fr", gap: 16 }}>
        <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
          <h3>{embedded ? "HACO dashboard module" : "Price chart + deterministic HACO buy/sell flips"}</h3>
          <div ref={chartRef} />
        </div>
        {!embedded ? <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
          <h3>Signal state summary</h3>
          <div>HACO state: {summary?.current_haco_state ?? "-"}</div>
          <div>Latest flip: {summary?.latest_flip ?? "-"}</div>
          <div>Flip recency (bars): {summary?.latest_flip_bars_ago ?? "-"}</div>
          <div>HACOLT direction: {summary?.current_hacolt_direction ?? "-"}</div>
        </div> : null}
      </div>

      <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
        <h3>HACO state strip (green/red)</h3>
        <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          {data?.haco_strip.slice(-80).map((p) => <div key={`${p.index}-${p.time}`} title={`${p.time} (#${p.index})`} style={{ width: 8, height: 16, background: p.state === "green" ? "#21c06e" : "#c64242" }} />)}
        </div>
      </div>
      <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
        <h3>HACOLT direction strip</h3>
        <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          {data?.hacolt_strip.slice(-80).map((p) => <div key={`${p.index}-${p.time}`} title={`${p.time} (#${p.index})`} style={{ width: 8, height: 12, background: p.direction === "up" ? "#4d8dff" : "#7a4dc1" }} />)}
        </div>
      </div>
      {embedded ? <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
        <strong>Signal summary:</strong> HACO {summary?.current_haco_state ?? "-"}, HACOLT {summary?.current_hacolt_direction ?? "-"}, latest flip {summary?.latest_flip ?? "-"}
      </div> : null}
    </div>
  );
}
