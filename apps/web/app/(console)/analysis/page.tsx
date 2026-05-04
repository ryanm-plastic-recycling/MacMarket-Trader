"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { WorkflowChart } from "@/components/charts/workflow-chart";
import { ExpectedRangeVisualization } from "@/components/options/expected-range-visualization";
import { MetricLabel } from "@/components/ui/metric-help";
import { fetchHacoChart, type HacoChartPayload } from "@/lib/haco-api";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { fetchStrategyRegistry, filterStrategiesByMode, type MarketMode, type StrategyRegistryEntry } from "@/lib/strategy-registry";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, GUIDED_FLOW_LABEL, parseGuidedFlowState } from "@/lib/guided-workflow";
import { formatExpectedMoveSummary } from "@/lib/analysis-expected-range";
import { SYMBOL_ENTRY_HELP_COPY } from "@/lib/symbol-entry";
import { WorkflowBanner } from "@/components/workflow-banner";
import {
  formatResearchCell,
  formatOptionsOpeningPriceSource,
  formatOptionsExpectedRangeHorizon,
  formatResearchTimestamp,
  formatResearchValue,
  getOptionsChainIncompleteSideWarning,
  getOptionsChainPreviewNotes,
  getOptionsChainUnavailableMessage,
  getOptionsLegDisplayLines,
  getOptionsPremiumLabel,
  getOptionsPremiumValue,
  getOptionsResearchDisplayDte,
  isReadOnlyResearchMode,
  type AnalysisPacket,
  type OptionsReadinessState,
  type OptionsResearchStructure,
} from "@/lib/recommendations";

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
  option_structure?: OptionsResearchStructure;
  structure_readiness?: OptionsReadinessState | string | null;
  structure_readiness_summary?: string | null;
  expected_range_readiness?: OptionsReadinessState | string | null;
  expected_range_readiness_summary?: string | null;
  paper_open_readiness?: OptionsReadinessState | string | null;
  paper_open_readiness_summary?: string | null;
  workbench_readiness_summary?: string | null;
  expected_range?: {
    method?: string | null;
    reference_price_type?: string | null;
    absolute_move?: number | null;
    lower_bound?: number | null;
    upper_bound?: number | null;
    horizon_value?: number | null;
    horizon_unit?: string | null;
    snapshot_timestamp?: string | null;
    provenance_notes?: string | null;
    status: "computed" | "blocked" | "omitted";
    reason?: string | null;
  } | null;
  options_chain_preview?: {
    underlying: string;
    expiry?: string | null;
    calls?: Array<{ strike: number | null; expiry: string | null; last_price: number | null; volume: number | null }> | null;
    puts?: Array<{ strike: number | null; expiry: string | null; last_price: number | null; volume: number | null }> | null;
    data_as_of?: string | null;
    source?: string | null;
    reason?: string | null;
  };
  analysis_packet?: AnalysisPacket | null;
};

const STORAGE_KEY = "macmarket-indicators-analysis";
const PROVIDER_BLOCKED_HINT = "Configured provider unavailable. Workflows are blocked from silently falling back. For local demo testing only, set WORKFLOW_DEMO_FALLBACK=true and restart backend.";

function normalizeOptionsReadiness(value: unknown): OptionsReadinessState {
  if (value === "ready" || value === "blocked" || value === "warning" || value === "unavailable") {
    return value;
  }
  return "unavailable";
}

function formatOptionsReadiness(value: OptionsReadinessState): string {
  if (value === "warning") return "Warning";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatExpectedRangeReadiness(value: OptionsReadinessState, status?: string | null): string {
  if (value === "ready") return status === "computed" ? "Computed" : "Ready";
  if (value === "warning") return "Stale context";
  if (value === "blocked") return "Blocked";
  return "Unavailable";
}

function formatPaperOpenReadiness(value: OptionsReadinessState): string {
  if (value === "blocked") return "Blocked fresh marks required";
  return formatOptionsReadiness(value);
}

function AnalysisContextPanels({ packet, optionStructure }: { packet?: AnalysisPacket | null; optionStructure?: OptionsResearchStructure | null }) {
  const macroSeries = packet?.macro_context?.series ?? [];
  const macroMissing = packet?.macro_context?.missing_data ?? [];
  const headlines = packet?.news_context?.headlines ?? [];
  const newsMissing = packet?.news_context?.missing_data ?? [];
  const indexPoints = packet?.index_context?.indices ?? [];
  const indexMissing = packet?.index_context?.missing_data ?? [];
  const optionLegs = optionStructure?.legs ?? [];
  return (
    <div className="op-grid-2">
      <Card title="Macro Context">
        {macroSeries.length > 0 ? (
          <div style={{ display: "grid", gap: 6 }}>
            {macroSeries.slice(0, 6).map((point) => (
              <div key={point.series_id} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span>{point.label}</span>
                <span style={{ color: "var(--op-muted, #7a8999)" }}>
                  {formatResearchValue(point.latest_value, "Not available from provider")}
                  {point.latest_date ? ` · ${point.latest_date}` : ""}
                  {point.stale ? " · stale" : ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--op-muted, #7a8999)" }}>
            Not available from provider{macroMissing.length > 0 ? `: ${macroMissing.join(", ")}` : ""}
          </div>
        )}
      </Card>
      <Card title="News Context">
        {headlines.length > 0 ? (
          <div style={{ display: "grid", gap: 8 }}>
            {headlines.slice(0, 5).map((item, index) => (
              <div key={`${item.title}-${index}`}>
                <div style={{ fontWeight: 600 }}>{item.title}</div>
                <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                  {[item.publisher, item.published_utc?.slice(0, 10), item.sentiment].filter(Boolean).join(" · ")}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--op-muted, #7a8999)" }}>
            Not available from provider{newsMissing.length > 0 ? `: ${newsMissing.join(", ")}` : ""}
          </div>
        )}
      </Card>
      <Card title="Index Context">
        {indexPoints.length > 0 ? (
          <div style={{ display: "grid", gap: 6 }}>
            {indexPoints.slice(0, 5).map((point) => (
              <div key={point.symbol} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span>{point.symbol} ({point.label})</span>
                <span style={{ color: "var(--op-muted, #7a8999)" }}>
                  {formatResearchValue(point.latest_value, "Not available from provider")}
                  {" | "}
                  {formatResearchValue(point.day_change_pct, "-")}%
                  {point.stale ? " | stale" : ""}
                </span>
              </div>
            ))}
            {packet?.index_context?.risk_summary ? (
              <div style={{ color: "var(--op-muted, #7a8999)" }}>Backdrop: {packet.index_context.risk_summary}</div>
            ) : null}
          </div>
        ) : (
          <div style={{ color: "var(--op-muted, #7a8999)" }}>
            Not available from provider{indexMissing.length > 0 ? `: ${indexMissing.join(", ")}` : ""}
          </div>
        )}
      </Card>
      {optionLegs.length > 0 ? (
        <Card title="Selected contract snapshots">
          <div className="op-table-scroll">
            <table className="op-table">
              <thead><tr><th>Leg</th><th>Strike snap</th><th>Mark</th><th>IV / OI</th><th>Greeks</th></tr></thead>
              <tbody>
                {optionLegs.map((leg, index) => (
                  <tr key={`${leg.option_symbol ?? leg.label ?? "leg"}-${index}`}>
                    <td>{leg.label ?? "leg"}<br /><span style={{ color: "var(--op-muted, #7a8999)" }}>{leg.option_symbol ?? "Missing from selected contract snapshot"}</span></td>
                    <td>
                      target {formatResearchValue(leg.target_strike, "Unavailable")}<br />
                      selected {formatResearchValue(leg.selected_listed_strike ?? leg.strike, "Unavailable")}<br />
                      <span style={{ color: "var(--op-muted, #7a8999)" }}>
                        snap {formatResearchValue(leg.strike_snap_distance, "Unavailable")} / allowed {formatResearchValue(leg.strike_snap_allowed, "Unavailable")}
                      </span>
                    </td>
                    <td>
                      {formatResearchValue(leg.current_mark_premium, "Missing from selected contract snapshot")}<br />
                      <span style={{ color: "var(--op-muted, #7a8999)" }}>
                        {leg.mark_method ?? "mark method missing"}
                        {leg.premium_source ? ` | premium source ${formatOptionsOpeningPriceSource(leg.premium_source)}` : ""}
                      </span>
                    </td>
                    <td>IV {formatResearchValue(leg.implied_volatility, "Missing from selected contract snapshot")}<br />OI {formatResearchValue(leg.open_interest, "Missing from selected contract snapshot")}</td>
                    <td>
                      delta {formatResearchValue(leg.delta, "Missing from selected contract snapshot")}<br />
                      gamma {formatResearchValue(leg.gamma, "Missing from selected contract snapshot")} · theta {formatResearchValue(leg.theta, "Missing from selected contract snapshot")} · vega {formatResearchValue(leg.vega, "Missing from selected contract snapshot")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

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
  const e2eBypass = isE2EAuthBypassEnabled();
  const authReady = e2eBypass || (isLoaded && isSignedIn);
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
  const optionStructure = setup?.option_structure ?? null;
  const analysisPacket = setup?.analysis_packet ?? null;
  const optionPremiumLabel = getOptionsPremiumLabel(optionStructure);
  const optionPremiumValue = getOptionsPremiumValue(optionStructure);
  const researchPreviewQuery = buildGuidedQuery({
    guided: guidedMode,
    symbol: appliedSymbol,
    strategy: appliedStrategy,
    marketMode: appliedMarketMode,
    source: setup?.workflow_source ?? source,
  });
  const researchPreviewHref = researchPreviewQuery ? `/recommendations?${researchPreviewQuery}` : "/recommendations";
  const expectedRange = setup?.expected_range ?? null;
  const optionDisplayDte = getOptionsResearchDisplayDte(optionStructure, expectedRange);
  const optionsChainPreview = setup?.options_chain_preview ?? null;
  const optionsChainUnavailableMessage = getOptionsChainUnavailableMessage(optionsChainPreview);
  const optionsChainIncompleteSideWarning = getOptionsChainIncompleteSideWarning(optionsChainPreview);
  const optionsChainPreviewNotes = getOptionsChainPreviewNotes(optionsChainPreview);
  const expectedRangeHorizon = formatOptionsExpectedRangeHorizon(expectedRange, optionStructure);
  const optionStructureBreakevens = optionStructure
    ? [optionStructure.breakeven_low, optionStructure.breakeven_high].filter(
      (value): value is number => typeof value === "number" && Number.isFinite(value),
    )
    : [];
  const structureReadiness = normalizeOptionsReadiness(optionStructure?.structure_readiness ?? setup?.structure_readiness);
  const expectedRangeReadiness = normalizeOptionsReadiness(optionStructure?.expected_range_readiness ?? setup?.expected_range_readiness);
  const paperOpenReadiness = normalizeOptionsReadiness(optionStructure?.paper_open_readiness ?? setup?.paper_open_readiness);
  const structureReadinessSummary = optionStructure?.structure_readiness_summary ?? setup?.structure_readiness_summary ?? null;
  const expectedRangeReadinessSummary = optionStructure?.expected_range_readiness_summary ?? setup?.expected_range_readiness_summary ?? null;
  const paperOpenReadinessSummary = optionStructure?.paper_open_readiness_summary ?? setup?.paper_open_readiness_summary ?? null;
  const optionsWorkbenchState =
    optionStructure?.workbench_readiness_summary
    ?? setup?.workbench_readiness_summary
    ?? null;

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
          Index data entitlement may be required. MacMarket will not silently fall back to an ETF substitute.
        </div>
      </div>
    ) : null}

    <Card>
      <div className="op-grid-4">
        <div>
          <label>Symbol</label>
          <input value={draftSymbol} onChange={(e) => setDraftSymbol(e.target.value.toUpperCase())} />
          <div style={{ marginTop: 4, color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", lineHeight: 1.4 }}>
            {SYMBOL_ENTRY_HELP_COPY.singleSymbolHint}
          </div>
        </div>
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
        <div><strong>Workbench state:</strong> {appliedMarketMode === "options" && optionsWorkbenchState ? optionsWorkbenchState : workbenchState.replaceAll("_", " ")}</div>
        <div><strong>Active/inactive:</strong> {setup?.active ? "active" : "inactive"} — {setup?.active_reason ?? "loading"}</div>
        <div><strong>Selected strategy:</strong> {appliedStrategy}</div>
        <div><strong>Symbol / mode / timeframe:</strong> {appliedSymbol} / {appliedMarketMode} / {appliedTimeframe}</div>
        <div><strong><MetricLabel label="Workflow source" term="provider_readiness" />:</strong> {formatResearchValue(setup?.workflow_source ?? source, "Source unavailable")}</div>
        {setup?.operator_guidance ? <div><strong>Mode guidance:</strong> {setup.operator_guidance}</div> : null}
        <div><strong>Summary:</strong> {setupSummary ?? "loading"}</div>
        {appliedMarketMode === "options" && optionStructure ? (
          <div>
            <div><strong>Structure readiness:</strong> {formatOptionsReadiness(structureReadiness)}{structureReadinessSummary ? ` — ${structureReadinessSummary}` : ""}</div>
            <div><strong>Expected Range readiness:</strong> {formatExpectedRangeReadiness(expectedRangeReadiness, expectedRange?.status)}{expectedRangeReadinessSummary ? ` — ${expectedRangeReadinessSummary}` : ""}</div>
            <div><strong>Paper Open readiness:</strong> {formatPaperOpenReadiness(paperOpenReadiness)}{paperOpenReadinessSummary ? ` — ${paperOpenReadinessSummary}` : ""}</div>
            <div><strong>Structure:</strong> {formatResearchValue(optionStructure.type)}</div>
            <div><strong>Legs:</strong> {getOptionsLegDisplayLines(optionStructure).join(" | ")}</div>
            <div><strong>{optionPremiumLabel}:</strong> {formatResearchValue(optionPremiumValue)}</div>
            <div><strong><MetricLabel label="Max profit" term="max_profit" /> / <MetricLabel label="Max loss" term="max_loss" />:</strong> {formatResearchValue(optionStructure.max_profit)} / {formatResearchValue(optionStructure.max_loss)}</div>
            <div><strong><MetricLabel label="Breakevens" term="breakeven" />:</strong> {formatResearchValue(optionStructure.breakeven_low)} - {formatResearchValue(optionStructure.breakeven_high)}</div>
            <div><strong>Expiration / <MetricLabel label="DTE" term="dte" />:</strong> {formatResearchValue(optionStructure.expiration)} / {formatResearchValue(optionDisplayDte)}</div>
            <div><strong><MetricLabel label="IV snapshot" term="iv" />:</strong> {formatResearchValue(optionStructure.iv_snapshot)}</div>
          </div>
        ) : (
          <>
            <div><strong><MetricLabel label="Confidence" term="confidence" />/filter state:</strong> {setup?.confidence ?? "-"} · {(setup?.filters ?? []).join(", ")}</div>
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
                ? "Options research stays read-only in the current paper-only scope. Use Recommendations to review the contract preview and paper lifecycle tools; equity queue and replay workflows remain separate."
                : "This market mode stays read-only in the current build. Persisted recommendations remain equities-only."}
            </div>
          ) : null}
        </div>
      </Card>
      <Card title="Expected move">
        {expectedRange ? (
          <>
            <div><strong><MetricLabel label="Expected Range status" term="expected_range" />:</strong> {formatResearchValue(expectedRange.status)}</div>
            <div><strong>Method:</strong> {formatResearchValue(expectedRange.method, "Source unavailable")}</div>
            <div><strong>Reference price:</strong> {formatResearchValue(expectedRange.reference_price_type, "Source unavailable")}</div>
            <div><strong>As-of:</strong> {formatResearchTimestamp(expectedRange.snapshot_timestamp ?? null)}</div>
            <div><strong><MetricLabel label="Expected Move" term="expected_range" />:</strong> {formatResearchValue(expectedRange.absolute_move)} ({formatResearchValue(expectedRange.lower_bound)} to {formatResearchValue(expectedRange.upper_bound)})</div>
            <div><strong><MetricLabel label="Horizon / DTE" term="dte" />:</strong> {expectedRangeHorizon}</div>
            <div><strong>Source notes:</strong> {formatResearchValue(expectedRange.provenance_notes, "Source unavailable")}</div>
            {expectedRange.reason ? <div><strong>Reason:</strong> {expectedRange.reason}</div> : null}
            <div>{formatExpectedMoveSummary(expectedRange, expectedRangeHorizon)}</div>
            {appliedMarketMode === "options" ? (
              <div style={{ marginTop: 10 }}>
                <ExpectedRangeVisualization
                  expectedRange={expectedRange}
                  breakevens={optionStructureBreakevens}
                  expiration={optionStructure?.expiration ?? null}
                  dte={optionDisplayDte}
                  maxProfit={optionStructure?.max_profit ?? null}
                  maxLoss={optionStructure?.max_loss ?? null}
                  workflowSource={setup?.workflow_source ?? source}
                  readiness={expectedRangeReadiness}
                  readinessSummary={expectedRangeReadinessSummary}
                />
              </div>
            ) : null}
          </>
        ) : (
          <>
            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.88rem" }}>
              Expected move data unavailable for this setup. Source unavailable. As-of unavailable.
            </div>
            {appliedMarketMode === "options" ? (
              <div style={{ marginTop: 10 }}>
                <ExpectedRangeVisualization
                  expectedRange={null}
                  breakevens={optionStructureBreakevens}
                  expiration={optionStructure?.expiration ?? null}
                  dte={optionStructure?.dte ?? null}
                  maxProfit={optionStructure?.max_profit ?? null}
                  maxLoss={optionStructure?.max_loss ?? null}
                  workflowSource={setup?.workflow_source ?? source}
                  readiness={expectedRangeReadiness}
                  readinessSummary={expectedRangeReadinessSummary}
                />
              </div>
            ) : null}
          </>
        )}
      </Card>
    </div>

    {setup ? <AnalysisContextPanels packet={analysisPacket} optionStructure={optionStructure} /> : null}

    {appliedMarketMode === "options" && setup?.options_chain_preview !== undefined ? (
      <Card title="Options chain preview">
        {optionsChainPreview?.reason ? (
          <div style={{ display: "grid", gap: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.88rem" }}>
            <div>{optionsChainUnavailableMessage}</div>
            <div>Provider plan or payload may not include this data. Index data entitlement may be required for SPX/NDX; MacMarket will not silently substitute SPY/QQQ.</div>
            <div>Source unavailable. As-of unavailable.</div>
          </div>
        ) : optionsChainPreview === null ? (
          <div style={{ display: "grid", gap: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.88rem" }}>
            <div>{optionsChainUnavailableMessage}</div>
            <div>Provider plan or payload may not include this data. Index data entitlement may be required for SPX/NDX; MacMarket will not silently substitute SPY/QQQ.</div>
            <div>Source unavailable. As-of unavailable.</div>
          </div>
        ) : (
          <>
            <div style={{ fontSize: "0.85rem", marginBottom: 8 }}>
              <strong>Underlying:</strong> {formatResearchValue(optionsChainPreview.underlying)}
              {optionsChainPreview.expiry ? <> &nbsp; <strong>Nearest expiry:</strong> {optionsChainPreview.expiry}</> : null}
              <> &nbsp; <strong><MetricLabel label="Source" term="provider_readiness" />:</strong> {formatResearchValue(optionsChainPreview.source, "Source unavailable")}</>
              <> &nbsp; <strong><MetricLabel label="As-of" term="provider_readiness" />:</strong> {formatResearchTimestamp(optionsChainPreview.data_as_of ?? null)}</>
            </div>
            <div className="op-grid-2" style={{ gap: 12 }}>
              <div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Calls</div>
                {optionsChainPreview.calls && optionsChainPreview.calls.length > 0 ? (
                  <table className="op-table">
                    <thead><tr><th>strike</th><th>expiry</th><th>last</th><th>volume</th></tr></thead>
                    <tbody>
                      {optionsChainPreview.calls.map((contract, i) => {
                        const c = {
                          strike: formatResearchCell(contract.strike),
                          expiry: formatResearchCell(contract.expiry),
                          last_price: formatResearchCell(contract.last_price),
                          volume: formatResearchCell(contract.volume),
                        };
                        return (
                        <tr key={i}>
                          <td>{c.strike ?? "—"}</td>
                          <td>{c.expiry ?? "—"}</td>
                          <td>{c.last_price ?? "—"}</td>
                          <td>{c.volume ?? "—"}</td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>No call contracts returned.</div>}
              </div>
              <div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Puts</div>
                {optionsChainPreview.puts && optionsChainPreview.puts.length > 0 ? (
                  <table className="op-table">
                    <thead><tr><th>strike</th><th>expiry</th><th>last</th><th>volume</th></tr></thead>
                    <tbody>
                      {optionsChainPreview.puts.map((contract, i) => {
                        const p = {
                          strike: formatResearchCell(contract.strike),
                          expiry: formatResearchCell(contract.expiry),
                          last_price: formatResearchCell(contract.last_price),
                          volume: formatResearchCell(contract.volume),
                        };
                        return (
                        <tr key={i}>
                          <td>{p.strike ?? "—"}</td>
                          <td>{p.expiry ?? "—"}</td>
                          <td>{p.last_price ?? "—"}</td>
                          <td>{p.volume ?? "—"}</td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>No put contracts returned.</div>}
              </div>
            </div>
            {optionsChainIncompleteSideWarning ? (
              <div style={{ marginTop: 6, fontSize: "0.78rem", color: "#f7b267" }}>
                {optionsChainIncompleteSideWarning}
              </div>
            ) : null}
            {optionsChainPreviewNotes.map((note) => (
              <div key={note} style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
                {note}
              </div>
            ))}
            {!optionsChainPreview.data_as_of ? (
              <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
                Reference data as of As-of unavailable. Chain preview unavailable fields may reflect provider plan or payload coverage. Research preview only; no execution support.
              </div>
            ) : null}
            {optionsChainPreview.data_as_of ? (
              <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
                Reference data as of {formatResearchTimestamp(optionsChainPreview.data_as_of)}. Research preview only; no execution support.
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
