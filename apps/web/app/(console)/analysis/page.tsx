"use client";

import { createChart, LineStyle, type CandlestickData, type IChartApi, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchHacoChart } from "@/lib/haco-api";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS } from "@/lib/chart-indicators";
import { fetchStrategyRegistry, filterStrategiesByMode, type MarketMode, type StrategyRegistryEntry } from "@/lib/strategy-registry";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, GUIDED_FLOW_LABEL, parseGuidedFlowState } from "@/lib/guided-workflow";
import { formatExpectedMoveSummary } from "@/lib/analysis-expected-range";

const SUPPORTED_TIMEFRAMES = ["1D", "4H", "1H"] as const;

type SupportedTimeframe = (typeof SUPPORTED_TIMEFRAMES)[number];
type WorkbenchState = "auth_initializing" | "loading_analysis" | "ready" | "fallback_mode" | "provider_unavailable" | "hard_failure";

type SetupPayload = {
  market_mode: MarketMode;
  workflow_source: string;
  strategy: string;
  strategy_metadata?: StrategyRegistryEntry;
  status?: string;
  execution_enabled?: boolean;
  operator_guidance?: string;
  active: boolean;
  active_reason: string;
  trigger: string;
  entry_zone: { low: number; high: number };
  invalidation: { price: number; reason: string };
  targets: number[];
  confidence: number;
  filters: string[];
  timeframe?: string;
  option_structure?: {
    type: string;
    legs: Array<{ action: string; right: string; strike: number; label: string }>;
    net_credit: number;
    max_profit: number;
    max_loss: number;
    breakeven_low: number;
    breakeven_high: number;
    dte: number;
    iv_snapshot: number;
  };
  expected_range?: {
    method?: string | null;
    absolute_move?: number | null;
    lower_bound?: number | null;
    upper_bound?: number | null;
    horizon_value?: number | null;
    horizon_unit?: string | null;
    status: "computed" | "blocked" | "omitted";
    reason?: string | null;
  };
};

const STORAGE_KEY = "macmarket-indicators-analysis";
const PROVIDER_BLOCKED_HINT = "Configured provider unavailable. Workflows are blocked from silently falling back. For local demo testing only, set WORKFLOW_DEMO_FALLBACK=true and restart backend.";

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  const [draftSymbol, setDraftSymbol] = useState("AAPL");
  const [draftMarketMode, setDraftMarketMode] = useState<MarketMode>("equities");
  const [draftTimeframe, setDraftTimeframe] = useState<SupportedTimeframe>("1D");
  const [draftStrategy, setDraftStrategy] = useState("Event Continuation");

  const [appliedSymbol, setAppliedSymbol] = useState("AAPL");
  const [appliedMarketMode, setAppliedMarketMode] = useState<MarketMode>("equities");
  const [appliedTimeframe, setAppliedTimeframe] = useState<SupportedTimeframe>("1D");
  const [appliedStrategy, setAppliedStrategy] = useState("Event Continuation");
  const [strategyRegistry, setStrategyRegistry] = useState<StrategyRegistryEntry[]>([]);

  const [source, setSource] = useState("workflow pending");
  const [setup, setSetup] = useState<SetupPayload | null>(null);
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);
  const [unsupportedIndicators, setUnsupportedIndicators] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [workbenchState, setWorkbenchState] = useState<WorkbenchState>("auth_initializing");
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const [showOperatorDetail, setShowOperatorDetail] = useState(false);
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const guidedState = useMemo(() => parseGuidedFlowState(searchParams), [searchParams]);
  const guidedMode = guidedState.guided;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    try {
      const parsed = raw ? (JSON.parse(raw) as string[]) : [];
      const normalized = normalizeSelection(parsed);
      const unsupported = normalized.filter((id) => !FIRST_CLASS_WORKFLOW_INDICATORS.includes(id));
      setUnsupportedIndicators(unsupported);
      setSelectedIndicators(normalized.filter((id) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(id)));
    } catch {
      setUnsupportedIndicators([]);
      setSelectedIndicators(normalizeSelection([]).filter((id) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(id)));
    }
  }, []);

  function setIndicators(next: IndicatorId[]) {
    const normalized = normalizeSelection(next).filter((id) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(id));
    setUnsupportedIndicators([]);
    setSelectedIndicators(normalized);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    }
  }

  const runAnalysis = async (nextSymbol: string, nextMode: MarketMode, nextTimeframe: SupportedTimeframe, nextStrategy: string) => {
    if (!authReady || !chartRef.current) {
      setWorkbenchState("auth_initializing");
      setFeedback({ state: "loading", message: "Authentication session is initializing for protected workbench routes…" });
      return;
    }

    setWorkbenchState("loading_analysis");
    setFeedback({ state: "loading", message: "Loading strategy setup and chart context…" });

    try {
      const setupResult = await fetchWorkflowApi<SetupPayload>(
        `/api/user/analysis/setup?req_symbol=${nextSymbol}&strategy=${encodeURIComponent(nextStrategy)}&timeframe=${nextTimeframe}&market_mode=${nextMode}`,
        undefined
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
      const chart = createChart(chartRef.current, { height: 380, autoSize: true, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
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

      if (setupPayload?.entry_zone && nextMode === "equities") {
        const entry = chart.addLineSeries({ color: "#6ea8fe", lineWidth: 2 });
        const stop = chart.addLineSeries({ color: "#ff8b8b", lineStyle: LineStyle.Dashed, lineWidth: 2 });
        const target = chart.addLineSeries({ color: "#7ee787", lineStyle: LineStyle.Dotted, lineWidth: 2 });
        entry.setData(candles.map((c) => ({ time: c.time, value: (setupPayload.entry_zone.low + setupPayload.entry_zone.high) / 2 })));
        stop.setData(candles.map((c) => ({ time: c.time, value: setupPayload.invalidation.price })));
        if (setupPayload.targets[0]) {
          target.setData(candles.map((c) => ({ time: c.time, value: setupPayload.targets[0] })));
        }
      }
      chart.timeScale().fitContent();

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
    if (!authReady || initialLoadDone) return;
    setInitialLoadDone(true);
    void runAnalysis(appliedSymbol, appliedMarketMode, appliedTimeframe, appliedStrategy);
  }, [isLoaded, isSignedIn, initialLoadDone, appliedSymbol, appliedMarketMode, appliedTimeframe, appliedStrategy]);

  useEffect(() => {
    if (!initialLoadDone) return;
    void runAnalysis(appliedSymbol, appliedMarketMode, appliedTimeframe, appliedStrategy);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndicators]);

  useEffect(() => () => chartApiRef.current?.remove(), []);
  useEffect(() => {
    if (feedback.state !== "success") return;
    const timer = window.setTimeout(() => setFeedback({ state: "idle", message: "" }), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback.state, feedback.message]);

  useEffect(() => {
    if (!authReady) return;
    void fetchStrategyRegistry().then((rows) => setStrategyRegistry(rows)).catch(() => setStrategyRegistry([]));
  }, [isLoaded, isSignedIn]);

  const strategiesForDraftMode = useMemo(() => filterStrategiesByMode(strategyRegistry, draftMarketMode), [strategyRegistry, draftMarketMode]);
  useEffect(() => {
    if (strategiesForDraftMode.length === 0) return;
    if (!strategiesForDraftMode.some((item) => item.display_name === draftStrategy)) {
      setDraftStrategy(strategiesForDraftMode[0].display_name);
    }
  }, [draftStrategy, strategiesForDraftMode]);

  async function refreshAnalysis() {
    const nextSymbol = draftSymbol.trim().toUpperCase() || "AAPL";
    setAppliedSymbol(nextSymbol);
    setAppliedMarketMode(draftMarketMode);
    setAppliedTimeframe(draftTimeframe);
    setAppliedStrategy(draftStrategy);
    await runAnalysis(nextSymbol, draftMarketMode, draftTimeframe, draftStrategy);
  }

  async function createRecommendation() {
    if (appliedMarketMode !== "equities") {
      setFeedback({ state: "error", message: "Create recommendation is disabled for planned research preview modes (options/crypto)." });
      return;
    }
    setFeedback({ state: "loading", message: "Creating recommendation from workbench setup…" });
    const result = await fetchWorkflowApi<{ recommendation_id?: string; data?: { recommendation_id?: string } }>(
      "/api/user/recommendations/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: appliedSymbol, market_mode: appliedMarketMode, event_text: `Workbench strategy: ${appliedStrategy}` }),
      }
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
    if (recommendationId) {
      const query = buildGuidedQuery({
        guided: guidedMode,
        symbol: appliedSymbol,
        strategy: appliedStrategy,
        recommendationId,
      });
      router.push(`/recommendations?${query}`);
    }
  }

  const setupSummary = useMemo(() => {
    if (!setup) return null;
    return `Trigger: ${setup.trigger} · Entry ${setup.entry_zone.low}-${setup.entry_zone.high} · Invalidation ${setup.invalidation.price}`;
  }, [setup]);

  return <section className="op-stack">
    <PageHeader title="Trade Setup" subtitle="Primary setup workstation before Recommendations, Replay, and paper Orders." actions={<StatusBadge tone="neutral">{source}</StatusBadge>} />
    {guidedMode ? <Card title={GUIDED_FLOW_LABEL}><GuidedStepRail current="Analyze" /></Card> : null}
    <Card title="Operator workflow guidance">
      <ol>
        <li>Choose symbol, timeframe, and strategy family.</li>
        <li>Click <strong>Refresh analysis</strong> to run protected setup + chart requests.</li>
        <li>Review rationale and expected move context for the selected mode.</li>
        <li>Create recommendation (equities only), then validate in Replay and stage in Paper Orders.</li>
      </ol>
      <div className="op-row"><Link href="/recommendations"><button>Open Recommendations workspace</button></Link></div>
    </Card>

    {workbenchState === "provider_unavailable" ? <ErrorState title="Provider configured but unavailable" hint={PROVIDER_BLOCKED_HINT} /> : null}


    {unsupportedIndicators.length > 0 ? (
      <ErrorState
        title="Indicator availability note"
        hint={`Selected but not yet renderable on this chart: ${unsupportedIndicators.join(", ")}. Choose from supported indicators below.`}
      />
    ) : null}

    <Card>
      <div className="op-grid-4">
        <div><label>Symbol</label><input value={draftSymbol} onChange={(e) => setDraftSymbol(e.target.value.toUpperCase())} /></div>
        <div><label>Market mode</label><select value={draftMarketMode} onChange={(e) => setDraftMarketMode(e.target.value as MarketMode)}><option value="equities">equities</option><option value="options">options</option><option value="crypto">crypto</option></select></div>
        <div><label>Timeframe</label><select value={draftTimeframe} onChange={(e) => setDraftTimeframe(e.target.value as SupportedTimeframe)}>{SUPPORTED_TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}</select></div>
        <div><label>Strategy</label><select value={draftStrategy} onChange={(e) => setDraftStrategy(e.target.value)}>{strategiesForDraftMode.map((entry) => <option key={entry.strategy_id} value={entry.display_name}>{entry.display_name}</option>)}</select></div>
        <div className="op-row" style={{ alignItems: "end" }}><button data-testid="analysis-refresh-button" onClick={() => void refreshAnalysis()}>Refresh analysis</button></div>
      </div>
      {draftMarketMode !== "equities" ? <StatusBadge tone="warn">planned research preview</StatusBadge> : null}
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void refreshAnalysis()} />
    </Card>

    <Card title="Indicator panel">
      <div className="op-row"><button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button></div>
      {showOperatorDetail ? <IndicatorSelector selected={selectedIndicators} onChange={setIndicators} enabledIds={FIRST_CLASS_WORKFLOW_INDICATORS} /> : null}
    </Card>

    <div className="op-grid-2">
      <Card title="Strategy rationale">
        <div><strong>Workbench state:</strong> {workbenchState.replaceAll("_", " ")}</div>
        <div><strong>Active/inactive:</strong> {setup?.active ? "active" : "inactive"} — {setup?.active_reason ?? "loading"}</div>
        <div><strong>Selected strategy:</strong> {appliedStrategy}</div>
        <div><strong>Symbol / mode / timeframe:</strong> {appliedSymbol} / {appliedMarketMode} / {appliedTimeframe}</div>
        <div><strong>Workflow source:</strong> {setup?.workflow_source ?? source}</div>
        {setup?.operator_guidance ? <div><strong>Mode guidance:</strong> {setup.operator_guidance}</div> : null}
        <div><strong>Summary:</strong> {setupSummary ?? "loading"}</div>
        {appliedMarketMode === "options" && setup?.option_structure ? (
          <div>
            <div><strong>Structure:</strong> {setup.option_structure.type}</div>
            <div><strong>Legs:</strong> {setup.option_structure.legs.map((leg) => `${leg.action} ${leg.right} ${leg.strike}`).join(" | ")}</div>
            <div><strong>Net credit:</strong> {setup.option_structure.net_credit}</div>
            <div><strong>Max P/L:</strong> {setup.option_structure.max_profit} / {setup.option_structure.max_loss}</div>
            <div><strong>Breakevens:</strong> {setup.option_structure.breakeven_low} - {setup.option_structure.breakeven_high}</div>
            <div><strong>DTE / IV snapshot:</strong> {setup.option_structure.dte} / {setup.option_structure.iv_snapshot}</div>
          </div>
        ) : (
          <>
            <div><strong>Confidence/filter state:</strong> {setup?.confidence ?? "-"} · {(setup?.filters ?? []).join(", ")}</div>
            <div><strong>Targets:</strong> {setup?.targets?.join(" / ") ?? "-"}</div>
          </>
        )}
        <div className="op-row" style={{ marginTop: 8 }}><button data-testid="analysis-create-recommendation-button" disabled={appliedMarketMode !== "equities"} onClick={() => void createRecommendation()}>{appliedMarketMode === "equities" ? "Create recommendation from setup" : "Preview-only mode (recommendation promotion blocked)"}</button></div>
      </Card>
      <Card title="Expected move">
        {setup?.expected_range ? (
          <>
            <div><strong>Status:</strong> {setup.expected_range.status}</div>
            <div><strong>Method:</strong> {setup.expected_range.method ?? "-"}</div>
            <div><strong>Move:</strong> {setup.expected_range.absolute_move ?? "-"} ({setup.expected_range.lower_bound ?? "-"} to {setup.expected_range.upper_bound ?? "-"})</div>
            <div><strong>Horizon:</strong> {setup.expected_range.horizon_value ?? "-"} {setup.expected_range.horizon_unit ?? ""}</div>
            {setup.expected_range.reason ? <div><strong>Reason:</strong> {setup.expected_range.reason}</div> : null}
            <div>{formatExpectedMoveSummary(setup.expected_range)}</div>
          </>
        ) : <div>Expected move preview unavailable for this setup.</div>}
      </Card>
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
