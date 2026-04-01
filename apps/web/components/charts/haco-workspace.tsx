"use client";

import { createChart, type CandlestickData, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { fetchHacoChart, type HacoChartPayload } from "@/lib/haco-api";

function mockBars() {
  const out = [];
  const base = new Date("2026-01-01");
  for (let i = 0; i < 120; i += 1) {
    const t = new Date(base);
    t.setDate(base.getDate() + i);
    const px = 100 + i * 0.4 + Math.sin(i / 8) * 1.5;
    out.push({ date: t.toISOString().slice(0, 10), open: px, high: px + 1.7, low: px - 1.2, close: px + 0.6, volume: 1000000 + i * 1000, rel_volume: 1.2 });
  }
  return out;
}

export function HacoWorkspace({ token }: { token: string }) {
  const [symbol, setSymbol] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("1D");
  const [data, setData] = useState<HacoChartPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement | null>(null);

  async function load() {
    setLoading(true);
    try {
      const payload = await fetchHacoChart(token, { symbol, timeframe, include_heikin_ashi: true, bars: mockBars() });
      setData(payload);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!chartRef.current || !data) return;
    const chart: IChartApi = createChart(chartRef.current, { height: 420, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" }, grid: { vertLines: { color: "#1f2a36" }, horzLines: { color: "#1f2a36" } } });
    const candleSeries: ISeriesApi<"Candlestick"> = chart.addCandlestickSeries();
    const candles: CandlestickData<Time>[] = data.candles.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close }));
    candleSeries.setData(candles);
    candleSeries.setMarkers(
      data.markers.map((m) => ({
        time: m.time as Time,
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
  }, [data]);

  const summary = useMemo(() => data?.explanation, [data]);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={{ background: "#0e151d", color: "#d9e2ef", border: "1px solid #2b3642", padding: "8px 10px" }} />
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} style={{ background: "#0e151d", color: "#d9e2ef", border: "1px solid #2b3642", padding: "8px 10px" }}>
          <option value="1D">1D</option><option value="4H">4H</option><option value="1H">1H</option>
        </select>
        <button onClick={load} disabled={loading} style={{ background: "#2d6cdf", border: "none", color: "white", padding: "8px 12px" }}>{loading ? "Loading..." : "Load HACO"}</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
        <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
          <h3>Price chart + flips</h3>
          <div ref={chartRef} />
        </div>
        <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
          <h3>State summary</h3>
          <div>HACO: {summary?.current_haco_state ?? "-"}</div>
          <div>Latest flip: {summary?.latest_flip ?? "-"}</div>
          <div>Flip recency: {summary?.latest_flip_bars_ago ?? "-"}</div>
          <div>HACOLT: {summary?.current_hacolt_direction ?? "-"}</div>
        </div>
      </div>

      <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
        <h3>HACO strip</h3>
        <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          {data?.haco_strip.slice(-80).map((p) => <div key={p.time} title={p.time} style={{ width: 8, height: 22, background: p.state === "green" ? "#21c06e" : "#c64242" }} />)}
        </div>
      </div>
      <div style={{ border: "1px solid #26303a", background: "#0b1219", padding: 12 }}>
        <h3>HACOLT strip</h3>
        <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
          {data?.hacolt_strip.slice(-80).map((p) => <div key={p.time} title={p.time} style={{ width: 8, height: 14, background: p.direction === "up" ? "#4d8dff" : "#7a4dc1" }} />)}
        </div>
      </div>
    </div>
  );
}
