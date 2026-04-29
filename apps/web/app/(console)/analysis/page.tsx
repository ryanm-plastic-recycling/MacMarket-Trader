"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { WorkflowChart } from "@/components/charts/workflow-chart";
import { fetchHacoChart, type HacoChartPayload } from "@/lib/haco-api";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { fetchStrategyRegistry, filterStrategiesByMode, type MarketMode, type StrategyRegistryEntry } from "@/lib/strategy-registry";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, GUIDED_FLOW_LABEL, parseGuidedFlowState } from "@/lib/guided-workflow";
import { formatExpectedMoveSummary } from "@/lib/analysis-expected-range";
import { WorkflowBanner } from "@/components/workflow-banner";
import { isReadOnlyResearchMode } from "@/lib/recommendations";

const SUPPORTED_TIMEFRAMES = ["1D", "4H", "1H"] as const;

type SupportedTimeframe = (typeof SUPPORTED_TIMEFRAMES)[number];
type WorkbenchState = "auth_initializing" | "loading_analysis" | "ready" | "fallback_mode" | "provider_unavailable" | "data_not_entitled" | "hard_failure";

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
  options_chain_preview?: {
    underlying: string;
    expiry?: string | null;
    calls?: Array<{ strike: number | null; expiry: string | null; last_price: number | null; volume: number | null }> | null;
    puts?: Array<{ strike: number | null; expiry: string | null; last_price: number | null; volume: number | null }> | null;
    data_as_of?: string | null;
    source?: string | null;
    reason?: string | null;
  } | null;
};

const STORAGE_KEY = "macmarket-indicators-analysis";
const PROVIDER_BLOCKED_HINT = "Configured provider unavailable. Workflows are blocked from silently falling back. For local demo testing only, set WORKFLOW_DEMO_FALLBACK=true and restart backend.";

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

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
  const [chartPayload, setChartPayload] = useState<HacoChartPayload | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [workbenchState, setWorkbenchState] = useState<WorkbenchState>("auth_initializing");
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const guidedState = useMemo(() => parseGuidedFlowState(searchParams), [searchParams]);
  const guidedMode = guidedState.guided;

  const runAnalysis = async (nextSymbol: string, nextMode: MarketMode, nextTimeframe: SupportedTimeframe, nextStrategy: string): Promise<string | null> => {
    if (!authReady) {
      setWorkbenchState("auth_initializing");
      setFeedback({ state: "loading", message: "Authentication session is initializing for protected workbench routes…" });
      return null;
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
          return null;
        }
        if (setupResult.status === 402) {
          setWorkbenchState("data_not_entitled");
          setFeedback({ state: "idle", message: "" });
          return null;
        }
        if (setupResult.status === 503) {
          setWorkbenchState("provider_unavailable");
          setFeedback({ state: "error", message: PROVIDER_BLOCKED_HINT });
          return null;
        }
        setWorkbenchState("hard_failure");
        setFeedback({ state: "error", message: setupResult.error ?? "Unable to load workbench setup." });
        return null;
      }

      const setupPayload = setupResult.data;
      if (setupPayload) {
        setSetup(setupPayload);
        setSource(setupPayload.workflow_source || "workflow source pending");
      }

      const payload = await fetchHacoChart({ symbol: nextSymbol, timeframe: nextTimeframe, include_heikin_ashi: nextStrategy === "HACO Context" });
      setChartPayload(payload);
      const workflowSource = payload.fallback_mode ? `fallback (${payload.data_source})` : payload.data_source;
      setSource(workflowSource || "workflow source pending");

      setWorkbenchState(payload.fallback_mode ? "fallback_mode" : "ready");
      setFeedback({ state: "success", message: "Analysis loaded. Strategy and indicators are synced to one canonical bar series." });
      return workflowSource || setupPayload?.workflow_source || "workflow source pending";
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_NOT_READY") {
        setWorkbenchState("auth_initializing");
        setFeedback({ state: "loading", message: "Authentication bridge still initializing for chart context." });
        return null;
      }
      setWorkbenchState("hard_failure");
      setFeedback({ state: "error", message: "Failed to load chart context. Retry when provider/auth is ready." });
      return null;
    }
  };

  useEffect(() => {
    if (!authReady || initialLoadDone) return;
    setInitialLoadDone(true);
    void runAnalysis(appliedSymbol, appliedMarketMode, appliedTimeframe, appliedStrategy);
  }, [isLoaded, isSignedIn, initialLoadDone, appliedSymbol, appliedMarketMode, appliedTimeframe, appliedStrategy]);
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
  const selectedStrategyEntry = useMemo(() => strategiesForDraftMode.find((e) => e.display_name === draftStrategy) ?? null, [strategiesForDraftMode, draftStrategy]);
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
    const workflowSource = await runAnalysis(nextSymbol, draftMarketMode, draftTimeframe, draftStrategy);
    if (workflowSource == null) return;
    const query = buildGuidedQuery({
      guided: guidedMode,
      symbol: nextSymbol,
      strategy: draftStrategy,
      marketMode: draftMarketMode,
      source: workflowSource,
    });
    router.replace(query ? `/analysis?${query}` : "/analysis");
  }

  async function createRecommendation() {
    if (isReadOnlyResearchMode(appliedMarketMode)) {
      setFeedback({
        state: "error",
        message: "Options and crypto remain read-only in this phase. Open Recommendations for research preview instead of creating a persisted recommendation.",
      });
      return;
    }
    setFeedback({ state: "loading", message: "Creating recommendation from workbench setup…" });
    const result = await fetchWorkflowApi<{ recommendation_id?: string; data?: { recommendation_id?: string } }>(
      "/api/user/recommendations/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: appliedSymbol,
          strategy: appliedStrategy,
          timeframe: appliedTimeframe,
          market_mode: appliedMarketMode,
          workflow_source: setup?.workflow_source ?? source,
          source: setup?.workflow_source ?? source,
          event_text: `Workbench strategy: ${appliedStrategy}`,
        }),
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
        marketMode: appliedMarketMode,
        source: setup?.workflow_source ?? source,
        recommendationId,
      });
      router.push(`/recommendations?${query}`);
    }
  }

  const setupSummary = useMemo(() => {
    if (!setup) return null;
    return `Trigger: ${setup.trigger} · Entry ${setup.entry_zone.low}-${setup.entry_zone.high} · Invalidation ${setup.invalidation.price}`;
  }, [setup]);

  const overlayLevels = useMemo(
    () => [
      { label: "entry", value: setup ? (setup.entry_zone.low + setup.entry_zone.high) / 2 : null, color: "#6ea8fe", lineWidth: 2 },
      { label: "stop", value: setup?.invalidation.price ?? null, color: "#ff8b8b", lineStyle: 2, lineWidth: 2 },
      { label: "target", value: setup?.targets?.[0] ?? null, color: "#7ee787", lineStyle: 3, lineWidth: 2 },
    ],
    [setup],
  );
  const createRecommendationDisabled = isReadOnlyResearchMode(appliedMarketMode);
  const researchPreviewQuery = buildGuidedQuery({
    guided: guidedMode,
    symbol: appliedSymbol,
    strategy: appliedStrategy,
    marketMode: appliedMarketMode,
    source: setup?.workflow_source ?? source,
  });
  const researchPreviewHref = researchPreviewQuery ? `/recommendations?${researchPreviewQuery}` : "/recommendations";

  return <section className="op-stack">
    <PageHeader title="Trade Setup" subtitle="Primary setup workstation before Recommendations, Replay, and paper Orders." actions={<StatusBadge tone="neutral">{source}</StatusBadge>} />
    <WorkflowBanner
      current="Analyze"
      state={{
        ...guidedState,
        symbol: appliedSymbol,
        strategy: appliedStrategy,
        marketMode: appliedMarketMode,
        source: setup?.workflow_source ?? source,
      }}
      nextHref="/recommendations"
      nextLabel={createRecommendationDisabled ? "Open research preview" : "Go to Recommendation"}
      compact={!guidedMode}
    />
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

    {workbenchState === "data_not_entitled" ? (
      <div className="op-card" style={{ border: "1px dashed #7c6a20", background: "#2a2010", padding: "12px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <StatusBadge tone="warn">Data not available on current plan</StatusBadge>
        </div>
        <div style={{ fontSize: "0.88rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
          Data not available for <strong>{appliedSymbol}</strong> on current plan.
          Try <strong>SPY</strong> instead of <strong>SPX</strong>, or <strong>QQQ</strong> instead of <strong>NDX</strong>.
        </div>
      </div>
    ) : null}

    <Card>
      <div className="op-grid-4">
        <div><label>Symbol</label><input value={draftSymbol} onChange={(e) => setDraftSymbol(e.target.value.toUpperCase())} /></div>
        <div><label>Market mode</label><select value={draftMarketMode} onChange={(e) => setDraftMarketMode(e.target.value as MarketMode)}><option value="equities">Equities</option><option value="options">Options (research preview)</option><option value="crypto">Crypto (research preview)</option></select></div>
        <div><label>Timeframe</label><select value={draftTimeframe} onChange={(e) => setDraftTimeframe(e.target.value as SupportedTimeframe)}>{SUPPORTED_TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}</select></div>
        <div>
          <label>Strategy</label>
          <select value={draftStrategy} onChange={(e) => setDraftStrategy(e.target.value)}>{strategiesForDraftMode.map((entry) => <option key={entry.strategy_id} value={entry.display_name}>{entry.display_name}</option>)}</select>
          {selectedStrategyEntry?.description ? (
            <div data-testid="strategy-hint" style={{ marginTop: 4, fontSize: "12px", color: "var(--op-muted, #7a8999)", lineHeight: 1.4 }}>
              <div>{selectedStrategyEntry.description}</div>
              {selectedStrategyEntry.regime_fit ? <div style={{ marginTop: 2 }}>Best in: {selectedStrategyEntry.regime_fit}</div> : null}
            </div>
          ) : null}
        </div>
        <div className="op-row" style={{ alignItems: "end" }}><button data-testid="analysis-refresh-button" onClick={() => void refreshAnalysis()}>Refresh analysis</button></div>
      </div>
      {(draftMarketMode === "options" || draftMarketMode === "crypto") ? (
        <div style={{ marginTop: 8 }}>
          <StatusBadge tone="warn">Research preview</StatusBadge>
          <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.88rem", lineHeight: 1.5 }}>
            This mode generates research-preview analysis only. Recommendations, replay, and paper orders are not available for options or crypto in the current build.
          </div>
        </div>
      ) : null}
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void refreshAnalysis()} />
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
        <div style={{ marginTop: 8 }}>
          <div className="op-row">
            <button data-testid="analysis-create-recommendation-button" onClick={() => void createRecommendation()} disabled={createRecommendationDisabled}>Create recommendation from setup</button>
            {createRecommendationDisabled ? (
              <Link href={researchPreviewHref}><button type="button">Open read-only research preview</button></Link>
            ) : null}
          </div>
          {createRecommendationDisabled ? (
            <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>
              {appliedMarketMode === "options"
                ? "Options research stays read-only in Phase 8B. Use Recommendations to review the contract preview; queue, replay, and paper orders remain unavailable."
                : "This market mode stays read-only in the current build. Persisted recommendations remain equities-only."}
            </div>
          ) : null}
        </div>
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
        ) : <div>Expected move data unavailable for this setup.</div>}
      </Card>
    </div>

    {appliedMarketMode === "options" && setup?.options_chain_preview !== undefined ? (
      <Card title="Options chain preview">
        {setup.options_chain_preview === null || setup.options_chain_preview?.reason ? (
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.88rem" }}>
            {setup.options_chain_preview?.reason ?? "Options chain data unavailable — Polygon options plan not configured."}
          </div>
        ) : (
          <>
            <div style={{ fontSize: "0.85rem", marginBottom: 8 }}>
              <strong>Underlying:</strong> {setup.options_chain_preview.underlying}
              {setup.options_chain_preview.expiry ? <> &nbsp; <strong>Nearest expiry:</strong> {setup.options_chain_preview.expiry}</> : null}
              {setup.options_chain_preview.source ? <> &nbsp; <span style={{ color: "var(--op-muted, #7a8999)" }}>({setup.options_chain_preview.source})</span></> : null}
            </div>
            <div className="op-grid-2" style={{ gap: 12 }}>
              <div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Calls</div>
                {setup.options_chain_preview.calls && setup.options_chain_preview.calls.length > 0 ? (
                  <table className="op-table">
                    <thead><tr><th>strike</th><th>expiry</th><th>last</th><th>volume</th></tr></thead>
                    <tbody>
                      {setup.options_chain_preview.calls.map((c, i) => (
                        <tr key={i}>
                          <td>{c.strike ?? "—"}</td>
                          <td>{c.expiry ?? "—"}</td>
                          <td>{c.last_price ?? "—"}</td>
                          <td>{c.volume ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>No call contracts returned.</div>}
              </div>
              <div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Puts</div>
                {setup.options_chain_preview.puts && setup.options_chain_preview.puts.length > 0 ? (
                  <table className="op-table">
                    <thead><tr><th>strike</th><th>expiry</th><th>last</th><th>volume</th></tr></thead>
                    <tbody>
                      {setup.options_chain_preview.puts.map((p, i) => (
                        <tr key={i}>
                          <td>{p.strike ?? "—"}</td>
                          <td>{p.expiry ?? "—"}</td>
                          <td>{p.last_price ?? "—"}</td>
                          <td>{p.volume ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>No put contracts returned.</div>}
              </div>
            </div>
            {setup.options_chain_preview.data_as_of ? (
              <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
                Reference data as of {setup.options_chain_preview.data_as_of}. Research preview — no execution support.
              </div>
            ) : null}
          </>
        )}
      </Card>
    ) : null}

    <Card title="Workbench chart">
      {!isLoaded || workbenchState === "auth_initializing"
        ? <EmptyState title="Auth initializing" hint="Waiting for authenticated session before loading protected market context." />
        : null}
      {workbenchState === "hard_failure" ? <ErrorState title="Analysis failed" hint="Retry analysis after checking provider health and auth state." /> : null}
      <WorkflowChart
        chartPayload={chartPayload}
        storageKey={STORAGE_KEY}
        overlayLevels={overlayLevels}
        emptyTitle="No chart context loaded"
        emptyHint="Refresh analysis to render price context, presets, and indicator hover values."
        sourceLabel={setup?.workflow_source ?? source}
      />
    </Card>
  </section>;
}
