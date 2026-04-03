"use client";

import { createChart, LineStyle, type CandlestickData, type IChartApi, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchHacoChart } from "@/lib/haco-api";
import { fetchWorkflowApi } from "@/lib/api-client";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS } from "@/lib/chart-indicators";

const STRATEGIES = [
  "Event Continuation",
  "Breakout / Prior-Day High",
  "Pullback / Trend Continuation",
  "Gap Follow-Through",
  "Mean Reversion",
  "HACO Context",
] as const;

const SUPPORTED_TIMEFRAMES = ["1D", "4H", "1H"] as const;

type StrategyName = (typeof STRATEGIES)[number];
type SupportedTimeframe = (typeof SUPPORTED_TIMEFRAMES)[number];
type WorkbenchState = "auth_initializing" | "loading_analysis" | "ready" | "fallback_mode" | "provider_unavailable" | "hard_failure";

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
  timeframe?: string;
};

const STORAGE_KEY = "macmarket-indicators-analysis";
const PROVIDER_BLOCKED_HINT = "Configured provider unavailable. Workflows are blocked from silently falling back. For local demo testing only, set WORKFLOW_DEMO_FALLBACK=true and restart backend.";

export default function Page() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const router = useRouter();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  const [draftSymbol, setDraftSymbol] = useState("AAPL");
  const [draftTimeframe, setDraftTimeframe] = useState<SupportedTimeframe>("1D");
  const [draftStrategy, setDraftStrategy] = useState<StrategyName>("Event Continuation");

  const [appliedSymbol, setAppliedSymbol] = useState("AAPL");
  const [appliedTimeframe, setAppliedTimeframe] = useState<SupportedTimeframe>("1D");
  const [appliedStrategy, setAppliedStrategy] = useState<StrategyName>("Event Continuation");

  const [source, setSource] = useState("workflow pending");
  const [setup, setSetup] = useState<SetupPayload | null>(null);
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [workbenchState, setWorkbenchState] = useState<WorkbenchState>("auth_initializing");
  const [initialLoadDone, setInitialLoadDone] = useState(false);

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
    const normalized = normalizeSelection(next).filter((id) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(id));
    setSelectedIndicators(normalized);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    }
  }

  const runAnalysis = async (nextSymbol: string, nextTimeframe: SupportedTimeframe, nextStrategy: StrategyName) => {
    if (!isLoaded || !isSignedIn || !chartRef.current) {
      setWorkbenchState("auth_initializing");
      setFeedback({ state: "loading", message: "Authentication session is initializing for protected workbench routes…" });
      return;
    }

    setWorkbenchState("loading_analysis");
    setFeedback({ state: "loading", message: "Loading strategy setup and chart context…" });

    try {
      const setupResult = await fetchWorkflowApi<SetupPayload>(
        `/api/user/analysis/setup?req_symbol=${nextSymbol}&strategy=${encodeURIComponent(nextStrategy)}&timeframe=${nextTimeframe}`,
        undefined,
        { authMode: "token", getToken },
      );
      if (!setupResult.ok) {
        if (setupResult.authPending) {
          setWorkbenchState("auth_initializing");
          setFeedback({ state: "loading", message: "Authentication still initializing. Workbench will be ready shortly." });
          return;
        }
        if (setupResult.status === 503) {
          setWorkbenchState("provider_unavailable");
          setFeedback({ state: "error", message: PROVIDER_BLOCKED_HINT });
          return;
        }
        setWorkbenchState("hard_failure");
        setFeedback({ state: "error", message: setupResult.error ?? "Unable to load workbench setup." });
        return;
      }

      const setupPayload = setupResult.data;
      if (setupPayload) {
        setSetup(setupPayload);
        setSource(setupPayload.workflow_source || "workflow source pending");
      }

      const payload = await fetchHacoChart({ symbol: nextSymbol, timeframe: nextTimeframe, include_heikin_ashi: nextStrategy === "HACO Context" });
      const workflowSource = payload.fallback_mode ? `fallback (${payload.data_source})` : payload.data_source;
      setSource(workflowSource || "workflow source pending");

      if (chartApiRef.current) {
        chartApiRef.current.remove();
      }
      const chart = createChart(chartRef.current, { height: 380, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      chartApiRef.current = chart;

      const candles: Array<CandlestickData<Time> & { volume: number }> = payload.candles.slice(-180).map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      }));

      chart.addCandlestickSeries().setData(candles);
      applyIndicatorsToChart(chart, candles, selectedIndicators);

      if (setupPayload?.entry_zone) {
        const entry = chart.addLineSeries({ color: "#6ea8fe", lineWidth: 2 });
        const stop = chart.addLineSeries({ color: "#ff8b8b", lineStyle: LineStyle.Dashed, lineWidth: 2 });
        const target = chart.addLineSeries({ color: "#7ee787", lineStyle: LineStyle.Dotted, lineWidth: 2 });
        entry.setData(candles.map((c) => ({ time: c.time, value: (setupPayload.entry_zone.low + setupPayload.entry_zone.high) / 2 })));
        stop.setData(candles.map((c) => ({ time: c.time, value: setupPayload.invalidation.price })));
        if (setupPayload.targets[0]) {
          target.setData(candles.map((c) => ({ time: c.time, value: setupPayload.targets[0] })));
        }
      }

      setWorkbenchState(payload.fallback_mode ? "fallback_mode" : "ready");
      setFeedback({ state: "success", message: "Analysis loaded. Strategy and indicators are synced to one canonical bar series." });
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_NOT_READY") {
        setWorkbenchState("auth_initializing");
        setFeedback({ state: "loading", message: "Authentication bridge still initializing for chart context." });
        return;
      }
      setWorkbenchState("hard_failure");
      setFeedback({ state: "error", message: "Failed to load chart context. Retry when provider/auth is ready." });
    }
  };

  useEffect(() => {
    if (!isLoaded || !isSignedIn || initialLoadDone) return;
    setInitialLoadDone(true);
    void runAnalysis(appliedSymbol, appliedTimeframe, appliedStrategy);
  }, [isLoaded, isSignedIn, initialLoadDone, appliedSymbol, appliedTimeframe, appliedStrategy]);

  useEffect(() => {
    if (!initialLoadDone) return;
    void runAnalysis(appliedSymbol, appliedTimeframe, appliedStrategy);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndicators]);

  useEffect(() => () => chartApiRef.current?.remove(), []);

  async function refreshAnalysis() {
    const nextSymbol = draftSymbol.trim().toUpperCase() || "AAPL";
    setAppliedSymbol(nextSymbol);
    setAppliedTimeframe(draftTimeframe);
    setAppliedStrategy(draftStrategy);
    await runAnalysis(nextSymbol, draftTimeframe, draftStrategy);
  }

  async function createRecommendation() {
    setFeedback({ state: "loading", message: "Creating recommendation from workbench setup…" });
    const result = await fetchWorkflowApi<{ recommendation_id?: string; data?: { recommendation_id?: string } }>(
      "/api/user/recommendations/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: appliedSymbol, event_text: `Workbench strategy: ${appliedStrategy}` }),
      },
      { authMode: "token", getToken },
    );
    if (!result.ok) {
      if (result.status === 503) {
        setWorkbenchState("provider_unavailable");
        setFeedback({ state: "error", message: PROVIDER_BLOCKED_HINT });
        return;
      }
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
    <Card title="Operator workflow guidance">
      <ol>
        <li>Choose symbol, timeframe, and strategy family.</li>
        <li>Click <strong>Refresh analysis</strong> to run protected setup + chart requests.</li>
        <li>Review rationale, levels, and active indicators.</li>
        <li>Create recommendation, then validate in Replay and stage in Paper Orders.</li>
      </ol>
      <div className="op-row"><Link href="/recommendations"><button>Open Recommendations workspace</button></Link></div>
    </Card>

    {workbenchState === "provider_unavailable" ? <ErrorState title="Provider configured but unavailable" hint={PROVIDER_BLOCKED_HINT} /> : null}

    <Card>
      <div className="op-grid-4">
        <div><label>Symbol</label><input value={draftSymbol} onChange={(e) => setDraftSymbol(e.target.value.toUpperCase())} /></div>
        <div><label>Timeframe</label><select value={draftTimeframe} onChange={(e) => setDraftTimeframe(e.target.value as SupportedTimeframe)}>{SUPPORTED_TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}</select></div>
        <div><label>Strategy</label><select value={draftStrategy} onChange={(e) => setDraftStrategy(e.target.value as StrategyName)}>{STRATEGIES.map((name) => <option key={name} value={name}>{name}</option>)}</select></div>
        <div className="op-row" style={{ alignItems: "end" }}><button onClick={() => void refreshAnalysis()}>Refresh analysis</button></div>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void refreshAnalysis()} />
    </Card>

    <Card title="Indicator panel"><IndicatorSelector selected={selectedIndicators} onChange={setIndicators} enabledIds={FIRST_CLASS_WORKFLOW_INDICATORS} /></Card>

    <div className="op-grid-2">
      <Card title="Strategy rationale">
        <div><strong>Workbench state:</strong> {workbenchState.replaceAll("_", " ")}</div>
        <div><strong>Active/inactive:</strong> {setup?.active ? "active" : "inactive"} — {setup?.active_reason ?? "loading"}</div>
        <div><strong>Selected strategy:</strong> {appliedStrategy}</div>
        <div><strong>Symbol / timeframe:</strong> {appliedSymbol} / {appliedTimeframe}</div>
        <div><strong>Workflow source:</strong> {setup?.workflow_source ?? source}</div>
        <div><strong>Summary:</strong> {setupSummary ?? "loading"}</div>
        <div><strong>Confidence/filter state:</strong> {setup?.confidence ?? "-"} · {(setup?.filters ?? []).join(", ")}</div>
        <div><strong>Targets:</strong> {setup?.targets?.join(" / ") ?? "-"}</div>
        <div className="op-row" style={{ marginTop: 8 }}><button onClick={() => void createRecommendation()}>Create recommendation from setup</button></div>
      </Card>
      <Card title="Enabled indicators">{selectedIndicators.map((indicator) => <StatusBadge key={indicator} tone="neutral">{indicator}</StatusBadge>)}</Card>
    </div>

    <Card title="Workbench chart">
      {!isLoaded || workbenchState === "auth_initializing"
        ? <EmptyState title="Auth initializing" hint="Waiting for authenticated session before loading protected market context." />
        : null}
      {workbenchState === "hard_failure" ? <ErrorState title="Analysis failed" hint="Retry analysis after checking provider health and auth state." /> : null}
      <div ref={chartRef} />
    </Card>
  </section>;
}
