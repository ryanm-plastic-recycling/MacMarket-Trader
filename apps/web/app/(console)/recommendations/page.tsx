"use client";

import { createChart, LineStyle, type CandlestickData, type IChartApi, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { fetchHacoChart } from "@/lib/haco-api";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS } from "@/lib/chart-indicators";

type QueueCandidate = {
  rank: number;
  symbol: string;
  strategy: string;
  workflow_source: string;
  timeframe: string;
  status: string;
  score: number;
  expected_rr: number;
  confidence: number;
  reason_text: string;
  thesis: string;
};
type Rec = { id: number; created_at: string; symbol: string; payload: any; recommendation_id: string; market_data_source?: string; fallback_mode?: boolean };

const STORAGE_KEY = "macmarket-indicators-recommendations";

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  const [rows, setRows] = useState<Rec[]>([]);
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [selected, setSelected] = useState<QueueCandidate | null>(null);
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA,AMZN");
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);

  async function loadRecommendations() {
    const result = await fetchWorkflowApi<Rec>("/api/user/recommendations");
    if (result.ok) setRows(result.items);
  }

  async function loadQueue() {
    setFeedback({ state: "loading", message: "Refreshing ranked recommendation queue…" });
    const result = await fetchWorkflowApi<{ queue: QueueCandidate[] }>("/api/user/recommendations/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols: symbols.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean), timeframe: "1D", market_mode: "equities" }),
    });
    if (!result.ok || !result.data) {
      setError(result.error ?? "Unable to load ranked queue");
      setFeedback({ state: "error", message: result.error ?? "Unable to load ranked queue" });
      return;
    }
    setError(null);
    setQueue(result.data.queue);
    setSelected((prev) => result.data?.queue.find((item) => item.rank === prev?.rank) ?? result.data?.queue[0] ?? null);
    setFeedback({ state: "success", message: "Ranked queue updated." });
    await loadRecommendations();
  }

  async function promoteSelected() {
    if (!selected) return;
    setFeedback({ state: "loading", message: "Promoting queue candidate to recommendation…" });
    const result = await fetchWorkflowApi("/api/user/recommendations/queue/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(selected),
    });
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Promotion failed" });
      return;
    }
    setFeedback({ state: "success", message: "Queue candidate promoted to recommendation." });
    await loadRecommendations();
  }

  useEffect(() => {
    if (!authReady) return;
    void loadQueue();
  }, [authReady]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    try {
      setSelectedIndicators(normalizeSelection(raw ? (JSON.parse(raw) as string[]) : []).filter((item) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(item)));
    } catch {
      setSelectedIndicators(["ema20", "vwap", "prior_day_levels"]);
    }
  }, []);

  useEffect(() => {
    async function renderChart() {
      if (!chartRef.current || !selected) return;
      if (selected.workflow_source.includes("fallback")) return;
      const payload = await fetchHacoChart({ symbol: selected.symbol, timeframe: selected.timeframe, include_heikin_ashi: false });
      if (chartApiRef.current) chartApiRef.current.remove();
      const chart = createChart(chartRef.current, { height: 300, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      chartApiRef.current = chart;
      const candles: Array<CandlestickData<Time> & { volume: number }> = payload.candles.slice(-120).map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume }));
      chart.addCandlestickSeries().setData(candles);
      applyIndicatorsToChart(chart, candles, selectedIndicators);
      const scoreLine = chart.addLineSeries({ color: "#6ea8fe", lineStyle: LineStyle.Dotted, lineWidth: 2 });
      scoreLine.setData(candles.map((c) => ({ time: c.time, value: Number(c.close) * (1 + selected.score * 0.01) })));
    }
    void renderChart();
    return () => chartApiRef.current?.remove();
  }, [selected, selectedIndicators]);

  return (
    <section className="op-stack">
      <PageHeader title="Recommendations" subtitle="Ranked queue for operator review, promotion, replay, and paper-order prep." actions={<StatusBadge tone="neutral">Analysis → Recommendations → Replay → Orders</StatusBadge>} />
      <Card>
        <div className="op-row">
          <input value={symbols} onChange={(e) => setSymbols(e.target.value.toUpperCase())} style={{ minWidth: 320 }} />
          <button onClick={() => void loadQueue()}>Refresh queue</button>
          <button onClick={() => void promoteSelected()} disabled={!selected}>Promote selected</button>
          <button onClick={() => selected ? window.location.assign(`/replay-runs?symbol=${selected.symbol}`) : null} disabled={!selected}>Open replay</button>
          <button onClick={() => selected ? window.location.assign(`/orders?symbol=${selected.symbol}`) : null} disabled={!selected}>Open orders</button>
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadQueue()} />
      </Card>
      {error ? <ErrorState title="Queue unavailable" hint={error} /> : null}
      {!error && queue.length === 0 ? <EmptyState title="No queue candidates" hint="Refresh queue with at least one symbol." /> : null}
      <div className="op-grid-2">
        <Card title="Ranked queue">
          <table className="op-table"><thead><tr><th>rank</th><th>symbol</th><th>strategy</th><th>source</th><th>status</th><th>score</th><th>rr</th><th>confidence</th></tr></thead><tbody>
            {queue.map((row) => <tr key={`${row.symbol}-${row.strategy}-${row.rank}`} onClick={() => setSelected(row)} className={`is-selectable ${selected?.rank === row.rank ? "is-active" : ""}`}><td>{row.rank}</td><td>{row.symbol}</td><td>{row.strategy}</td><td>{row.workflow_source}</td><td>{row.status}</td><td>{row.score}</td><td>{row.expected_rr}</td><td>{row.confidence}</td></tr>)}
          </tbody></table>
        </Card>
        <Card title="Candidate detail">
          {!selected ? <EmptyState title="Select candidate" hint="Pick a ranked row." /> : <div className="op-detail-list">
            <div><strong>symbol/timeframe:</strong> {selected.symbol} / {selected.timeframe}</div>
            <div><strong>strategy:</strong> {selected.strategy}</div>
            <div><strong>source:</strong> {selected.workflow_source}</div>
            <div><strong>thesis:</strong> {selected.thesis}</div>
            <div><strong>status:</strong> {selected.status}</div>
            <div><strong>reason:</strong> {selected.reason_text}</div>
          </div>}
        </Card>
      </div>
      <Card title="Queue chart context">
        <IndicatorSelector selected={selectedIndicators} onChange={setSelectedIndicators} enabledIds={FIRST_CLASS_WORKFLOW_INDICATORS} />
        {selected?.workflow_source.includes("fallback") ? <StatusBadge tone="warn">fallback candidate: chart overlay disabled to avoid mixed-source context.</StatusBadge> : null}
        <div ref={chartRef} />
      </Card>
      <Card title="Persisted recommendations count"><strong>{rows.length}</strong> stored recommendations available for replay/order lineage.</Card>
    </section>
  );
}
