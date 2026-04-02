"use client";

import { createChart, type CandlestickData, LineStyle, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, EmptyState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchHacoChart } from "@/lib/haco-api";
import { fetchNormalizedAuthed } from "@/lib/api-client";

const STRATEGIES = [
  "Event Continuation",
  "Breakout / Prior-Day High",
  "Pullback / Trend Continuation",
  "Gap Follow-Through",
  "Mean Reversion",
  "HACO Context",
] as const;

type StrategyName = (typeof STRATEGIES)[number];

const STRATEGY_NOTES: Record<StrategyName, string> = {
  "Event Continuation": "Active when catalyst novelty is high and breadth supports continuation.",
  "Breakout / Prior-Day High": "Active when price reclaims and holds prior-day high with RVOL confirmation.",
  "Pullback / Trend Continuation": "Active when trend remains intact and pullback holds support.",
  "Gap Follow-Through": "Active when opening gap aligns with sector leadership and volume expansion.",
  "Mean Reversion": "Active only in chop/overextension conditions with clear invalidation.",
  "HACO Context": "Supporting context strategy; use as confirmation, not sole approval.",
};

export default function Page() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [symbol, setSymbol] = useState("AAPL");
  const [timeframe, setTimeframe] = useState("1D");
  const [strategy, setStrategy] = useState<StrategyName>("Event Continuation");
  const [source, setSource] = useState("initializing");
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });

  const levels = useMemo(() => ({ entry: 183.25, stop: 179.8, target1: 187.9, target2: 191.2, trigger: "Hold above prior day high with RVOL >= 1.4", confidence: "0.66 · Filters: breadth supportive, vol moderate" }), [strategy]);

  async function loadChart() {
    if (!isLoaded || !isSignedIn || !chartRef.current) {
      setFeedback({ state: "loading", message: "Waiting for auth session to initialize." });
      return;
    }
    setFeedback({ state: "loading", message: "Loading strategy context chart…" });
    try {
      const payload = await fetchHacoChart({ symbol, timeframe, include_heikin_ashi: strategy === "HACO Context" });
      const workflowSource = payload.fallback_mode ? `fallback (${payload.data_source})` : payload.data_source;
      setSource(workflowSource);
      const chart = createChart(chartRef.current, { height: 340, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      const candles: CandlestickData<Time>[] = payload.candles.slice(-120).map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close }));
      chart.addCandlestickSeries().setData(candles);
      const entry = chart.addLineSeries({ color: "#6ea8fe", lineWidth: 2 });
      const stop = chart.addLineSeries({ color: "#ff8b8b", lineStyle: LineStyle.Dashed, lineWidth: 2 });
      const target = chart.addLineSeries({ color: "#7ee787", lineStyle: LineStyle.Dotted, lineWidth: 2 });
      entry.setData(candles.map((c) => ({ time: c.time, value: levels.entry })));
      stop.setData(candles.map((c) => ({ time: c.time, value: levels.stop })));
      target.setData(candles.map((c) => ({ time: c.time, value: levels.target1 })));
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
    }).catch(() => {
      setFeedback({ state: "error", message: "Chart render failed." });
    });
    return () => cleanup?.();
  }, [isLoaded, isSignedIn, symbol, timeframe, strategy]);

  async function createRecommendation() {
    setFeedback({ state: "loading", message: "Creating recommendation from workbench setup…" });
    const result = await fetchNormalizedAuthed("/api/user/recommendations/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, event_text: `Workbench strategy: ${strategy}` }),
    }, getToken);
    if (!result.ok) {
      setFeedback({ state: "error", message: result.authPending ? "Authentication initializing. Please wait." : (result.error ?? "Create recommendation failed") });
      return;
    }
    setFeedback({ state: "success", message: "Recommendation created from selected setup." });
  }

  return <section className="op-stack">
    <PageHeader title="Analysis / Strategy Workbench" subtitle="Operator-grade setup builder before recommendation, replay, and paper orders." actions={<StatusBadge tone="neutral">{source}</StatusBadge>} />
    <Card>
      <div className="op-grid-4">
        <div><label>Symbol</label><input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} /></div>
        <div><label>Timeframe</label><select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}><option value="1D">1D</option><option value="1W">1W</option></select></div>
        <div><label>Strategy</label><select value={strategy} onChange={(e) => setStrategy(e.target.value as StrategyName)}>{STRATEGIES.map((name) => <option key={name} value={name}>{name}</option>)}</select></div>
        <div className="op-row" style={{ alignItems: "end" }}><button onClick={() => void loadChart()}>Refresh analysis</button></div>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadChart()} />
    </Card>

    <div className="op-grid-2">
      <Card title="Strategy rationale">
        <div><strong>Active/inactive notes:</strong> {STRATEGY_NOTES[strategy]}</div>
        <div><strong>Trigger:</strong> {levels.trigger}</div>
        <div><strong>Confidence/filters:</strong> {levels.confidence}</div>
        <div><strong>Entry:</strong> {levels.entry}</div>
        <div><strong>Stop:</strong> {levels.stop}</div>
        <div><strong>Targets:</strong> {levels.target1} / {levels.target2}</div>
        <div className="op-row" style={{ marginTop: 8 }}>
          <button onClick={() => void createRecommendation()}>Create recommendation from this setup</button>
        </div>
      </Card>
      <Card title="Source coherence">
        {source.includes("fallback") ? <StatusBadge tone="warn">Workflow source is fallback for this setup.</StatusBadge> : <StatusBadge tone="good">Provider-backed workflow source.</StatusBadge>}
        <p>Chart context and setup metadata share the same workflow source label to avoid mixed-context decisions.</p>
      </Card>
    </div>

    <Card title="Workbench chart">
      {!isLoaded ? <EmptyState title="Initializing auth" hint="Waiting for authenticated session before loading protected market context." /> : <div ref={chartRef} />}
    </Card>
  </section>;
}
