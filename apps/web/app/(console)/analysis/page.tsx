"use client";

import { createChart, type CandlestickData, LineStyle, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, EmptyState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchHacoChart } from "@/lib/haco-api";
import { fetchWorkflowApi } from "@/lib/api-client";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { calculateIndicatorSnapshot, normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";

const STRATEGIES = [
  "Event Continuation",
  "Breakout / Prior-Day High",
  "Pullback / Trend Continuation",
  "Gap Follow-Through",
  "Mean Reversion",
  "HACO Context",
] as const;

type StrategyName = (typeof STRATEGIES)[number];

type SetupPayload = {
  workflow_source: string;
  active: boolean;
  active_reason: string;
  trigger: string;
  entry_zone: { low: number; high: number };
  invalidation: { price: number; reason: string };
  targets: number[];
  confidence: number;
  filters: string[];
};

const STORAGE_KEY = "macmarket-indicators-analysis";

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [symbol, setSymbol] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("1D");
  const [strategy, setStrategy] = useState<StrategyName>("Event Continuation");
  const [source, setSource] = useState("initializing");
  const [setup, setSetup] = useState<SetupPayload | null>(null);
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    try {
      const parsed = raw ? (JSON.parse(raw) as string[]) : [];
      setSelectedIndicators(normalizeSelection(parsed));
    } catch {
      setSelectedIndicators(normalizeSelection([]));
    }
  }, []);

  function setIndicators(next: IndicatorId[]) {
    const normalized = normalizeSelection(next);
    setSelectedIndicators(normalized);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    }
  }

  async function loadChart() {
    if (!isLoaded || !isSignedIn || !chartRef.current) {
      return;
    }
    setFeedback({ state: "loading", message: "Loading strategy context chart…" });
    try {
      const setupResult = await fetchWorkflowApi<SetupPayload>(`/api/user/analysis/setup?req_symbol=${symbol}&strategy=${encodeURIComponent(strategy)}&timeframe=${timeframe}`);
      if (setupResult.ok && setupResult.data) {
        setSetup(setupResult.data);
        setSource(setupResult.data.workflow_source);
      }
      const payload = await fetchHacoChart({ symbol, timeframe, include_heikin_ashi: strategy === "HACO Context" });
      const workflowSource = payload.fallback_mode ? `fallback (${payload.data_source})` : payload.data_source;
      setSource(workflowSource);
      const chart = createChart(chartRef.current, { height: 360, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      const candles: CandlestickData<Time>[] = payload.candles.slice(-120).map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close }));
      chart.addCandlestickSeries().setData(candles);
      const snapshot = calculateIndicatorSnapshot(payload.candles.map((item) => ({ ...item, time: String(item.time) })));
      if (selectedIndicators.includes("ema20") && snapshot.ema20) {
        chart.addLineSeries({ color: "#6ea8fe", lineWidth: 2 }).setData(candles.map((c) => ({ time: c.time, value: snapshot.ema20 as number })));
      }
      if (selectedIndicators.includes("ema50") && snapshot.ema50) {
        chart.addLineSeries({ color: "#a78bfa", lineWidth: 1 }).setData(candles.map((c) => ({ time: c.time, value: snapshot.ema50 as number })));
      }
      if (setup?.entry_zone) {
        const entry = chart.addLineSeries({ color: "#6ea8fe", lineWidth: 2 });
        const stop = chart.addLineSeries({ color: "#ff8b8b", lineStyle: LineStyle.Dashed, lineWidth: 2 });
        const target = chart.addLineSeries({ color: "#7ee787", lineStyle: LineStyle.Dotted, lineWidth: 2 });
        entry.setData(candles.map((c) => ({ time: c.time, value: (setup.entry_zone.low + setup.entry_zone.high) / 2 })));
        stop.setData(candles.map((c) => ({ time: c.time, value: setup.invalidation.price })));
        target.setData(candles.map((c) => ({ time: c.time, value: setup.targets[0] })));
      }
      setFeedback({ state: "success", message: "Strategy chart ready." });
      return () => chart.remove();
    } catch {
      setFeedback({ state: "error", message: "Failed to load chart context. Retry when provider/auth is ready." });
    }
  }

  useEffect(() => {
    let cleanup: (() => void) | undefined;
    loadChart().then((c) => {
      cleanup = c;
    }).catch(() => setFeedback({ state: "error", message: "Chart render failed." }));
    return () => cleanup?.();
  }, [isLoaded, isSignedIn, symbol, timeframe, strategy, selectedIndicators]);

  async function createRecommendation() {
    setFeedback({ state: "loading", message: "Creating recommendation from workbench setup…" });
    const result = await fetchWorkflowApi<{ recommendation_id?: string; data?: { recommendation_id?: string } }>("/api/user/recommendations/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, event_text: `Workbench strategy: ${strategy}` }),
    });
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Create recommendation failed" });
      return;
    }
    setFeedback({ state: "success", message: "Recommendation created from selected setup." });
    const recommendationId =
      (result.raw as Record<string, unknown> | null)?.recommendation_id as string | undefined
      ?? (result.data as { recommendation_id?: string } | null)?.recommendation_id;
    if (recommendationId) router.push(`/recommendations?recommendation=${recommendationId}`);
  }

  const setupSummary = useMemo(() => {
    if (!setup) return null;
    return `Trigger: ${setup.trigger} · Entry ${setup.entry_zone.low}-${setup.entry_zone.high} · Invalidation ${setup.invalidation.price}`;
  }, [setup]);

  return <section className="op-stack">
    <PageHeader title="Analysis / Strategy Workbench" subtitle="Primary setup workstation before Recommendations, Replay, and paper Orders." actions={<StatusBadge tone="neutral">{source}</StatusBadge>} />
    <Card title="Operator workflow">
      <ol>
        <li>Choose symbol, timeframe, and strategy family.</li>
        <li>Review deterministic trigger, entry zone, invalidation, and targets.</li>
        <li>Enable only indicators needed for this setup.</li>
        <li>Create recommendation for execution prep review.</li>
      </ol>
      <div className="op-row"><Link href="/recommendations"><button>Open Recommendations workspace</button></Link></div>
    </Card>
    <Card>
      <div className="op-grid-4">
        <div><label>Symbol</label><input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} /></div>
        <div><label>Timeframe</label><select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}><option value="1D">1D</option><option value="1W">1W</option></select></div>
        <div><label>Strategy</label><select value={strategy} onChange={(e) => setStrategy(e.target.value as StrategyName)}>{STRATEGIES.map((name) => <option key={name} value={name}>{name}</option>)}</select></div>
        <div className="op-row" style={{ alignItems: "end" }}><button onClick={() => void loadChart()}>Refresh analysis</button></div>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadChart()} />
    </Card>

    <Card title="Indicator panel"><IndicatorSelector selected={selectedIndicators} onChange={setIndicators} /></Card>

    <div className="op-grid-2">
      <Card title="Strategy rationale">
        <div><strong>Active/inactive:</strong> {setup?.active ? "active" : "inactive"} — {setup?.active_reason ?? "loading"}</div>
        <div><strong>Selected strategy:</strong> {strategy}</div>
        <div><strong>Workflow source:</strong> {setup?.workflow_source ?? source}</div>
        <div><strong>Summary:</strong> {setupSummary ?? "loading"}</div>
        <div><strong>Confidence/filter state:</strong> {setup?.confidence ?? "-"} · {(setup?.filters ?? []).join(", ")}</div>
        <div><strong>Targets:</strong> {setup?.targets?.join(" / ") ?? "-"}</div>
        <div className="op-row" style={{ marginTop: 8 }}><button onClick={() => void createRecommendation()}>Create recommendation from this setup</button></div>
      </Card>
      <Card title="Enabled indicators">{selectedIndicators.map((indicator) => <StatusBadge key={indicator} tone="neutral">{indicator}</StatusBadge>)}</Card>
    </div>

    <Card title="Workbench chart">
      {!isLoaded ? <EmptyState title="Initializing auth" hint="Waiting for authenticated session before loading protected market context." /> : <div ref={chartRef} />}
    </Card>
  </section>;
}
