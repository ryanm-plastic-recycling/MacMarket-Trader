"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { WorkflowChart } from "@/components/charts/workflow-chart";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { fetchHacoChart, type HacoChartPayload } from "@/lib/haco-api";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, parseGuidedFlowState } from "@/lib/guided-workflow";
import { WorkflowBanner } from "@/components/workflow-banner";
import {
  getPromotedQueueKeys,
  getRankingProvenance,
  isFallbackWorkflow,
  parseRecommendationSearchParams,
  type QueueCandidate,
  type StoredRecommendation,
} from "@/lib/recommendations";

const STORAGE_KEY = "macmarket-indicators-recommendations";

type QueueSummary = {
  total: number;
  top_candidate_count: number;
  watchlist_count: number;
  no_trade_count: number;
};

function formatDate(dateStr: string): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr.slice(0, 10);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function asText(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function toNum(v: unknown): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

type RecLevels = { entryLow: number | null; entryHigh: number | null; stop: number | null; target1: number | null; target2: number | null };

function extractLevels(rec: StoredRecommendation | null, queue: QueueCandidate | null): RecLevels {
  const empty: RecLevels = { entryLow: null, entryHigh: null, stop: null, target1: null, target2: null };
  if (rec) {
    const p = rec.payload;
    const entry = p.entry as Record<string, unknown> | undefined;
    const inv = p.invalidation as Record<string, unknown> | undefined;
    const tgts = p.targets as Record<string, unknown> | undefined;
    return {
      entryLow: toNum(entry?.zone_low ?? entry?.low),
      entryHigh: toNum(entry?.zone_high ?? entry?.high),
      stop: toNum(inv?.price),
      target1: toNum(tgts?.target_1),
      target2: toNum(tgts?.target_2),
    };
  }
  if (queue) {
    const ez = queue.entry_zone as Record<string, unknown> | undefined;
    const inv = queue.invalidation as Record<string, unknown> | undefined;
    const tgts = queue.targets;
    return {
      entryLow: toNum(ez?.low ?? ez?.zone_low),
      entryHigh: toNum(ez?.high ?? ez?.zone_high),
      stop: toNum((inv as Record<string, unknown> | undefined)?.price),
      target1: Array.isArray(tgts) && tgts.length > 0 ? toNum(tgts[0]) : null,
      target2: Array.isArray(tgts) && tgts.length > 1 ? toNum(tgts[1]) : null,
    };
  }
  return empty;
}

export default function RecommendationsPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());

  const [rows, setRows] = useState<StoredRecommendation[]>([]);
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [queueSummary, setQueueSummary] = useState<QueueSummary | null>(null);
  const [selectedQueueKey, setSelectedQueueKey] = useState<string | null>(null);
  const [selectedRecommendationId, setSelectedRecommendationId] = useState<number | null>(null);
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA,AMZN");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState({ queue: false, recommendations: false, promote: false, saveAlt: false, approve: false });
  const [chartPayload, setChartPayload] = useState<HacoChartPayload | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [showOperatorDetail, setShowOperatorDetail] = useState(false);
  const [tableSymbolFilter, setTableSymbolFilter] = useState("");
  const [tableStrategyFilter, setTableStrategyFilter] = useState("");
  const [tableStatusFilter, setTableStatusFilter] = useState<"all" | "approved" | "rejected">("all");

  const prefill = useMemo(() => parseRecommendationSearchParams(searchParams), [searchParams]);
  const guidedState = useMemo(() => parseGuidedFlowState(searchParams), [searchParams]);
  const [showQueue, setShowQueue] = useState(!guidedState.guided);

  const selectedQueue = useMemo(
    () => queue.find((item) => `${item.symbol}-${item.strategy}-${item.rank}` === selectedQueueKey) ?? null,
    [queue, selectedQueueKey],
  );
  const selectedRecommendation = useMemo(
    () => rows.find((item) => item.id === selectedRecommendationId) ?? null,
    [rows, selectedRecommendationId],
  );
  const fallbackDerived = isFallbackWorkflow(selectedQueue, selectedRecommendation);
  const selectedSource = selectedRecommendation
    ? `${selectedRecommendation.market_data_source ?? asText((selectedRecommendation.payload.workflow as Record<string, unknown> | undefined)?.market_data_source)}`
    : selectedQueue?.workflow_source ?? "source pending";

  async function loadRecommendations(options?: { selectRecommendationUid?: string }) {
    setLoading((prev) => ({ ...prev, recommendations: true }));
    const result = await fetchWorkflowApi<StoredRecommendation>("/api/user/recommendations");
    setLoading((prev) => ({ ...prev, recommendations: false }));
    if (!result.ok) {
      setError(result.error ?? "Unable to load stored recommendations");
      return;
    }
    setError(null);
    setRows(result.items);

    const targetUid = options?.selectRecommendationUid ?? prefill.recommendationId;
    if (targetUid) {
      const matched = result.items.find((item) => item.recommendation_id === targetUid);
      if (matched) {
        setSelectedRecommendationId(matched.id);
        setSelectedQueueKey(null);
      }
    }
  }

  async function loadQueue(overrideSymbols?: string[]) {
    const activeSymbols = overrideSymbols?.length
      ? overrideSymbols
      : symbols
          .split(",")
          .map((item) => item.trim().toUpperCase())
          .filter(Boolean);
    if (!activeSymbols.length) {
      setQueue([]);
      return;
    }

    setLoading((prev) => ({ ...prev, queue: true }));
    setFeedback({ state: "loading", message: "Refreshing ranked recommendation queue…" });
    const result = await fetchWorkflowApi<{ queue: QueueCandidate[]; summary: QueueSummary }>("/api/user/recommendations/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols: activeSymbols, timeframe: "1D", market_mode: "equities" }),
    });
    setLoading((prev) => ({ ...prev, queue: false }));

    if (!result.ok || !result.data) {
      setError(result.error ?? "Unable to load ranked queue");
      setFeedback({ state: "error", message: result.error ?? "Unable to load ranked queue" });
      return;
    }

    setError(null);
    setQueue(result.data.queue);
    setQueueSummary(result.data.summary ?? null);
    setSelectedQueueKey((prev) => {
      const preserved = result.data?.queue.find((item) => `${item.symbol}-${item.strategy}-${item.rank}` === prev);
      if (preserved) return `${preserved.symbol}-${preserved.strategy}-${preserved.rank}`;
      const first = result.data?.queue[0];
      return first ? `${first.symbol}-${first.strategy}-${first.rank}` : null;
    });
    setFeedback({ state: "success", message: "Ranked queue updated." });
  }

  async function promoteSelected() {
    if (!selectedQueue) return;
    setLoading((prev) => ({ ...prev, promote: true }));
    setFeedback({ state: "loading", message: "Promoting queue candidate to recommendation…" });
    const result = await fetchWorkflowApi<{ recommendation_id: string }>("/api/user/recommendations/queue/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...selectedQueue, action: "make_active" }),
    });
    setLoading((prev) => ({ ...prev, promote: false }));

    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Promotion failed" });
      return;
    }

    setError(null);
    setFeedback({ state: "success", message: "Queue candidate promoted to stored recommendation." });
    // Defensive ID extraction: backend returns {recommendation_id, ...} at top level.
    // result.data unwraps a nested {data:{...}} envelope when present, otherwise it's the raw payload.
    // Fall back through raw and the selected queue candidate just in case the response shape shifts.
    const rawRec = (result.raw as { recommendation_id?: string } | null | undefined)?.recommendation_id;
    const queueRec = (selectedQueue as { recommendation_id?: string } | null | undefined)?.recommendation_id;
    const promotedRecommendationId = result.data?.recommendation_id ?? rawRec ?? queueRec;
    await loadRecommendations({ selectRecommendationUid: promotedRecommendationId });
    if (guidedState.guided && promotedRecommendationId) {
      const query = buildGuidedQuery({
        ...guidedState,
        symbol: selectedQueue?.symbol ?? guidedState.symbol,
        strategy: selectedQueue?.strategy ?? guidedState.strategy,
        marketMode: guidedState.marketMode ?? selectedQueue?.market_mode ?? "equities",
        source: selectedQueue?.workflow_source ?? guidedState.source,
        recommendationId: promotedRecommendationId,
      });
      router.replace(`/recommendations?${query}`);
      // Auto-advance: in guided mode the operator's next step is always Replay.
      // Brief delay so the success feedback is readable before the route changes.
      // Temporary debug log (will be removed in next pass) to help diagnose
      // the smoke-test report that auto-advance was not firing.
      console.debug("[guided] promote success, advancing to replay in 600ms", { promotedId: promotedRecommendationId, query });
      setTimeout(() => router.push(`/replay-runs?${query}`), 600);
    }
  }

  async function saveAlternative() {
    if (!selectedQueue) return;
    setLoading((prev) => ({ ...prev, saveAlt: true }));
    setFeedback({ state: "loading", message: "Saving queue candidate as alternative recommendation…" });
    const result = await fetchWorkflowApi<{ recommendation_id: string }>("/api/user/recommendations/queue/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...selectedQueue, action: "save_alternative" }),
    });
    setLoading((prev) => ({ ...prev, saveAlt: false }));

    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Save as alternative failed" });
      return;
    }

    setError(null);
    setFeedback({ state: "success", message: "Saved as alternative recommendation (not set as active)." });
    const savedRecommendationId = result.data?.recommendation_id;
    await loadRecommendations({ selectRecommendationUid: savedRecommendationId });
    // No guided state update — saving as alternative does not advance the lineage
  }

  function openReplay() {
    const symbol = selectedRecommendation?.symbol ?? selectedQueue?.symbol ?? guidedState.symbol;
    const strategy = selectedQueue?.strategy
      ?? (typeof selectedRecProvenance?.strategy === "string" ? selectedRecProvenance.strategy : guidedState.strategy);
    const recommendationId = selectedRecommendation?.recommendation_id ?? guidedState.recommendationId;
    const query = buildGuidedQuery({
      guided: guidedState.guided,
      symbol,
      strategy,
      marketMode: guidedState.marketMode ?? selectedQueue?.market_mode ?? "equities",
      source: selectedSource,
      recommendationId,
    });
    router.push(`/replay-runs?${query}`);
  }

  function openOrders() {
    const symbol = selectedRecommendation?.symbol ?? selectedQueue?.symbol ?? guidedState.symbol;
    const strategy = selectedQueue?.strategy
      ?? (typeof selectedRecProvenance?.strategy === "string" ? selectedRecProvenance.strategy : guidedState.strategy);
    const recommendationId = selectedRecommendation?.recommendation_id ?? guidedState.recommendationId;
    const query = buildGuidedQuery({
      guided: guidedState.guided,
      symbol,
      strategy,
      marketMode: guidedState.marketMode ?? selectedQueue?.market_mode ?? "equities",
      source: selectedSource,
      recommendationId,
    });
    router.push(`/orders?${query}`);
  }

  function openReplayGuidedCta() {
    if (selectedRecommendation?.recommendation_id) {
      openReplay();
    }
  }

  async function setApproval(approved: boolean) {
    if (!selectedRecommendation?.recommendation_id) return;
    setLoading((prev) => ({ ...prev, approve: true }));
    setFeedback({ state: "loading", message: approved ? "Approving recommendation…" : "Rejecting recommendation…" });
    const result = await fetchWorkflowApi<{ recommendation_id: string; approved: boolean }>(
      `/api/user/recommendations/${selectedRecommendation.recommendation_id}/approve`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      },
    );
    setLoading((prev) => ({ ...prev, approve: false }));
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Approval update failed" });
      return;
    }
    setFeedback({ state: "success", message: approved ? "Recommendation approved." : "Recommendation rejected." });
    await loadRecommendations({ selectRecommendationUid: selectedRecommendation.recommendation_id });
  }

  useEffect(() => {
    if (!authReady) return;
    void loadRecommendations();
  }, [authReady]);

  useEffect(() => {
    if (!authReady) return;
    const symbolsFromParams = prefill.symbols;
    if (!symbolsFromParams.length) {
      void loadQueue();
      return;
    }
    const joined = symbolsFromParams.join(",");
    setSymbols(joined);
    void loadQueue(symbolsFromParams);
  }, [authReady, prefill.symbols.join(",")]);

  useEffect(() => {
    if (!rows.length || !prefill.recommendationId) return;
    const match = rows.find((item) => item.recommendation_id === prefill.recommendationId);
    if (match) {
      setSelectedRecommendationId(match.id);
      setSelectedQueueKey(null);
    }
  }, [rows, prefill.recommendationId]);

  useEffect(() => {
    let cancelled = false;
    async function renderChart() {
      const chartSymbol = selectedRecommendation?.symbol ?? selectedQueue?.symbol;
      const timeframe = selectedQueue?.timeframe ?? "1D";
      if (!chartSymbol || fallbackDerived) {
        setChartPayload(null);
        return;
      }
      const payload = await fetchHacoChart({ symbol: chartSymbol, timeframe, include_heikin_ashi: false });
      if (cancelled) return;
      setChartPayload(payload);
    }
    void renderChart();
    return () => {
      cancelled = true;
    };
  }, [selectedQueue?.symbol, selectedQueue?.timeframe, selectedRecommendation?.symbol, selectedRecommendation?.id, selectedQueueKey, fallbackDerived]);

  const selectedRecProvenance = getRankingProvenance((selectedRecommendation?.payload as Record<string, unknown>) ?? null);
  const promotedKeys = useMemo(() => getPromotedQueueKeys(rows), [rows]);
  const unsupportedGuidedMode = Boolean(guidedState.guided && guidedState.marketMode && guidedState.marketMode !== "equities");
  const isPreviewMode = guidedState.marketMode === "options" || guidedState.marketMode === "crypto";
  const activeRecommendation = useMemo(() => {
    if (selectedRecommendation) return selectedRecommendation;
    if (guidedState.guided) {
      // Guided mode never silently fabricates lineage: require an explicit recommendation match.
      if (!guidedState.recommendationId) return null;
      return rows.find((item) => item.recommendation_id === guidedState.recommendationId) ?? null;
    }
    if (guidedState.recommendationId) return rows.find((item) => item.recommendation_id === guidedState.recommendationId) ?? null;
    return rows[0] ?? null;
  }, [guidedState.guided, guidedState.recommendationId, rows, selectedRecommendation]);
  const filteredRows = useMemo(
    () =>
      rows
        .filter((row) => {
          const prov = getRankingProvenance(row.payload as Record<string, unknown>);
          const workflow = (row.payload.workflow as Record<string, unknown> | undefined) ?? {};
          const strategy = typeof prov?.strategy === "string" ? prov.strategy : typeof workflow.source_strategy === "string" ? workflow.source_strategy : "";
          const approved = Boolean((row.payload as Record<string, unknown>)?.approved);
          const symbolOk = tableSymbolFilter ? row.symbol.toLowerCase().includes(tableSymbolFilter.toLowerCase()) : true;
          const strategyOk = tableStrategyFilter ? strategy.toLowerCase().includes(tableStrategyFilter.toLowerCase()) : true;
          const statusOk = tableStatusFilter === "all" ? true : tableStatusFilter === "approved" ? approved : !approved;
          return symbolOk && strategyOk && statusOk;
        })
        .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))),
    [rows, tableStatusFilter, tableStrategyFilter, tableSymbolFilter],
  );
  const chartOverlayLevels = useMemo(() => {
    const levels = extractLevels(selectedRecommendation, selectedQueue);
    return [
      { label: "entry low", value: levels.entryLow, color: "#21c06e", lineStyle: 2 },
      { label: "entry high", value: levels.entryHigh, color: "#21c06e", lineStyle: 2 },
      { label: "stop", value: levels.stop, color: "#f44336", lineStyle: 2, lineWidth: 2 },
      { label: "T1", value: levels.target1, color: "#4caf50", lineStyle: 2 },
      { label: "T2", value: levels.target2, color: "#4caf50", lineStyle: 1 },
    ];
  }, [selectedQueue, selectedRecommendation]);

  return (
    <section className="op-stack">
      <PageHeader
        title="Recommendations"
        subtitle="Step 2 of the guided paper-trade flow: review and promote Analysis setups (equities live-prep only)."
        actions={<StatusBadge tone={fallbackDerived ? "warn" : "neutral"}>{fallbackDerived ? "Fallback workflow context" : "Provider workflow context"}</StatusBadge>}
      />
      <WorkflowBanner
        current="Recommendation"
        state={{
          ...guidedState,
          symbol: selectedRecommendation?.symbol ?? selectedQueue?.symbol ?? guidedState.symbol,
          strategy: selectedQueue?.strategy ?? guidedState.strategy,
          marketMode: guidedState.marketMode ?? selectedQueue?.market_mode ?? "equities",
          source: selectedSource,
          recommendationId: selectedRecommendation?.recommendation_id ?? guidedState.recommendationId,
        }}
        backHref="/analysis"
        backLabel="Back to Analyze"
        nextHref="/replay-runs"
        nextLabel="Go to Replay step"
        nextDisabled={guidedState.guided && !selectedRecommendation?.recommendation_id}
        nextDisabledReason="Guided replay requires a persisted recommendation. Promote the selected queue candidate first."
        compact={!guidedState.guided}
      />
      {isPreviewMode ? (
        <Card title="Options & crypto — research preview only">
          <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.6 }}>
            Options and crypto recommendations are research preview only. The full recommendation → replay → paper order workflow is available for equities only.
          </div>
          <div style={{ marginTop: 10 }}>
            <Link href="/analysis?guided=1"><button>← Restart in equities mode</button></Link>
          </div>
        </Card>
      ) : null}
      {guidedState.guided && !isPreviewMode ? (
        <Card title="Guided flow progress">
          <GuidedStepRail current="Recommendation" />
          <div style={{ marginTop: 8 }}>
            Recommendations queue is equities-only in Phase 1. Options/crypto stop at research preview because replay/order semantics are not mode-native yet.
          </div>
          <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)" }}>
            Guided mode carries one active recommendation at a time.
          </div>
        </Card>
      ) : null}
      {guidedState.guided && !isPreviewMode ? (
        <Card title="Active recommendation">
          {activeRecommendation ? (
            <>
              <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{activeRecommendation.display_id ?? activeRecommendation.recommendation_id}</span></div>
              <div>
                <strong>symbol:</strong> {activeRecommendation.symbol} · <strong>strategy:</strong>{" "}
                {String(
                  getRankingProvenance(activeRecommendation.payload as Record<string, unknown>)?.strategy
                  ?? ((activeRecommendation.payload.workflow as Record<string, unknown> | undefined)?.source_strategy as string | undefined)
                  ?? "-",
                )}
              </div>
            </>
          ) : (
            <EmptyState title="No active recommendation" hint="Create from Analysis or promote one queue candidate to start guided replay." />
          )}
        </Card>
      ) : null}
      {guidedState.guided && !isPreviewMode ? (
        <Card title="Next action">
          <div>{selectedRecommendation?.recommendation_id ? "Run replay for the active persisted recommendation to validate deterministic path behavior before staging paper orders." : "Promote the selected queue candidate to persist lineage, then run replay."}</div>
          {unsupportedGuidedMode ? <ErrorState title="Research preview stops here" hint="Options and crypto are research preview only. Guided progression into Replay and Paper Orders is disabled outside equities." /> : null}
          <div className="op-row" style={{ marginTop: 8 }}>
            {selectedRecommendation?.recommendation_id ? (
              <button onClick={openReplayGuidedCta} disabled={unsupportedGuidedMode}>Go to Replay step</button>
            ) : (
              <>
                <button className="op-btn-primary-cta" onClick={() => void promoteSelected()} disabled={unsupportedGuidedMode || !selectedQueue || loading.promote || loading.saveAlt} title={loading.promote ? "Promotion in flight…" : undefined}>
                  {loading.promote ? "Promoting…" : "Make active →"}
                </button>
                <button className="op-btn op-btn-secondary" onClick={() => void saveAlternative()} disabled={unsupportedGuidedMode || !selectedQueue || loading.promote || loading.saveAlt} title={loading.saveAlt ? "Saving alternative…" : undefined}>
                  {loading.saveAlt ? "Saving…" : "Save as alternative"}
                </button>
              </>
            )}
          </div>
        </Card>
      ) : null}

      {!isPreviewMode ? <Card>
        <div className="op-row">
          <input value={symbols} onChange={(e) => setSymbols(e.target.value.toUpperCase())} style={{ minWidth: 320 }} placeholder="AAPL,MSFT,NVDA" />
          <button onClick={() => void loadQueue()} disabled={loading.queue}>Refresh queue</button>
          {!guidedState.guided ? (
            <button onClick={() => void promoteSelected()} disabled={!selectedQueue || loading.promote}>{loading.promote ? "Promoting…" : "Promote selected queue candidate"}</button>
          ) : null}
          <button onClick={openReplay} disabled={guidedState.guided ? !selectedRecommendation : (!selectedQueue && !selectedRecommendation)}>Go to Replay step</button>
          {!guidedState.guided ? <button onClick={openOrders} disabled={!selectedQueue && !selectedRecommendation}>Go to Paper Order step</button> : null}
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadQueue()} />
      </Card> : null}

      {!isPreviewMode && error ? <ErrorState title="Recommendations workflow unavailable" hint={error} /> : null}

      {!isPreviewMode ? <div className="op-grid-2">
        <Card title="Ranked queue candidates">
          {guidedState.guided ? (
            <div style={{ marginBottom: 8 }}>
              <button className="op-btn op-btn-ghost" onClick={() => setShowQueue((prev) => !prev)}>
                {showQueue ? "Hide recommendation queue" : `View recommendation queue (${queue.length})`}
              </button>
            </div>
          ) : null}
          {(!guidedState.guided || showQueue) ? <>
          {queueSummary ? (
            <div className="op-row" style={{ marginBottom: 8, flexWrap: "wrap", gap: 6 }}>
              <StatusBadge tone="good">{queueSummary.top_candidate_count} top candidate{queueSummary.top_candidate_count !== 1 ? "s" : ""}</StatusBadge>
              <StatusBadge tone="neutral">{queueSummary.watchlist_count} watchlist</StatusBadge>
              <StatusBadge tone="warn">{queueSummary.no_trade_count} no-trade</StatusBadge>
              <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", alignSelf: "center" }}>{queueSummary.total} total</span>
            </div>
          ) : null}
          {loading.queue && queue.length === 0 ? <EmptyState title="Loading queue" hint="Fetching ranked queue candidates." /> : null}
          {!loading.queue && queue.length === 0 ? <EmptyState title="No queue candidates" hint="Refresh queue with at least one symbol." /> : null}
          {queue.length > 0 ? (
            <table className="op-table">
              <thead><tr><th>rank</th><th>symbol</th><th>strategy</th><th>status</th><th>score</th><th>rr</th><th>conf</th><th></th></tr></thead>
              <tbody>
                {queue.map((row) => {
                  const key = `${row.symbol}-${row.strategy}-${row.rank}`;
                  const isPromoted = promotedKeys.has(key);
                  const statusTone = row.status === "top_candidate" ? "good" : row.status === "no_trade" ? "warn" : "neutral";
                  return (
                    <tr key={key} className={`is-selectable ${selectedQueueKey === key ? "is-active" : ""}`} onClick={() => { setSelectedQueueKey(key); setSelectedRecommendationId(null); }}>
                      <td>{row.rank}</td>
                      <td>{row.symbol}</td>
                      <td>{row.strategy}</td>
                      <td><StatusBadge tone={statusTone}>{row.status.replace(/_/g, " ")}</StatusBadge></td>
                      <td>{row.score}</td>
                      <td>{row.expected_rr}</td>
                      <td>{row.confidence}</td>
                      <td>{isPromoted ? <StatusBadge tone="good">promoted</StatusBadge> : null}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : null}
          </> : null}
        </Card>

        <Card title="Persisted recommendations">
          <div className="op-row" style={{ marginBottom: 8, flexWrap: "wrap" }}>
            <input placeholder="Filter symbol" value={tableSymbolFilter} onChange={(e) => setTableSymbolFilter(e.target.value)} />
            <input placeholder="Filter strategy" value={tableStrategyFilter} onChange={(e) => setTableStrategyFilter(e.target.value)} />
            <select value={tableStatusFilter} onChange={(e) => setTableStatusFilter(e.target.value as "all" | "approved" | "rejected")}>
              <option value="all">All statuses</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
          {loading.recommendations && rows.length === 0 ? <EmptyState title="Loading recommendations" hint="Fetching stored recommendations." /> : null}
          {!loading.recommendations && rows.length === 0 ? <EmptyState title="No stored recommendations" hint="Promote a queue candidate to create reviewable lineage." /> : null}
          {rows.length > 0 ? (
            <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
            <table className="op-table">
              <thead><tr><th>date</th><th>symbol</th><th>strategy</th><th>queue rank</th><th>approved</th><th>source</th></tr></thead>
              <tbody>
                {filteredRows.map((row) => {
                  const prov = getRankingProvenance(row.payload as Record<string, unknown>);
                  const strategy = typeof prov?.strategy === "string" ? prov.strategy : (typeof (row.payload.workflow as Record<string, unknown> | undefined)?.source_strategy === "string" ? String((row.payload.workflow as Record<string, unknown>).source_strategy) : "-");
                  const rank = prov?.rank != null ? `#${String(prov.rank)}` : "-";
                  const approved = (row.payload as Record<string, unknown>)?.approved;
                  return (
                    <tr key={row.id} className={`is-selectable ${selectedRecommendationId === row.id ? "is-active" : ""}`} onClick={() => { setSelectedRecommendationId(row.id); setSelectedQueueKey(null); }}>
                      <td>{formatDate(row.created_at)}</td>
                      <td>{row.symbol}</td>
                      <td>{strategy}</td>
                      <td>{rank}</td>
                      <td>{approved == null ? "-" : approved ? <StatusBadge tone="good">approved</StatusBadge> : <StatusBadge tone="warn">rejected</StatusBadge>}</td>
                      <td>{row.market_data_source ?? asText((row.payload.workflow as Record<string, unknown> | undefined)?.market_data_source)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          ) : null}
        </Card>
      </div> : null}

      {!isPreviewMode ? <div className="op-grid-2">
        <Card title="Queue candidate detail">
          {guidedState.guided ? <div className="op-row" style={{ marginBottom: 8 }}><button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button></div> : null}
          {!selectedQueue ? <EmptyState title="No queue selection" hint="Select a queue row to review deterministic ranking detail." /> : (
            <div className="op-detail-list">
              <div><strong>rank:</strong> {selectedQueue.rank}</div>
              <div><strong>symbol:</strong> {selectedQueue.symbol}</div>
              <div><strong>strategy:</strong> {selectedQueue.strategy}</div>
              <div><strong>timeframe:</strong> {selectedQueue.timeframe}</div>
              <div><strong>market_mode:</strong> {selectedQueue.market_mode ?? "equities"}</div>
              {!guidedState.guided || showOperatorDetail ? (
                <>
                  <div><strong>workflow source:</strong> {selectedQueue.workflow_source}{selectedQueue.source && selectedQueue.source !== selectedQueue.workflow_source ? ` (${selectedQueue.source})` : ""}</div>
                  <div><strong>status:</strong> {selectedQueue.status.replace(/_/g, " ")}</div>
                  <div><strong>score:</strong> {selectedQueue.score}</div>
                  <div><strong>expected rr:</strong> {selectedQueue.expected_rr} &nbsp; <strong>confidence:</strong> {selectedQueue.confidence}</div>
                  <div><strong>thesis:</strong> {selectedQueue.thesis}</div>
                  <div><strong>reason:</strong> {selectedQueue.reason_text}</div>
                  <div><strong>trigger:</strong> {asText(selectedQueue.trigger)}</div>
                  <div><strong>entry zone:</strong> {asText(selectedQueue.entry_zone)}</div>
                  <div><strong>invalidation:</strong> {asText(selectedQueue.invalidation)}</div>
                  <div><strong>targets:</strong> {asText(selectedQueue.targets)}</div>
                  {selectedQueue.score_breakdown ? (
                    <div><strong>score breakdown:</strong>{" "}
                      {Object.entries(selectedQueue.score_breakdown).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}
                    </div>
                  ) : null}
                </>
              ) : (
                <div style={{ color: "var(--op-muted, #7a8999)" }}>Advanced operator ranking detail is collapsed in guided mode.</div>
              )}
              <div style={{ marginTop: 12, paddingTop: 8, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
                {promotedKeys.has(`${selectedQueue.symbol}-${selectedQueue.strategy}-${selectedQueue.rank}`) ? (
                  <StatusBadge tone="good">Already promoted to recommendation</StatusBadge>
                ) : (
                  <div className="op-row">
                    <button className="op-btn op-btn-primary" onClick={() => void promoteSelected()} disabled={loading.promote || loading.saveAlt} title={loading.promote ? "Promotion in flight…" : undefined}>
                      {loading.promote ? "Promoting…" : "Make active"}
                    </button>
                    <button className="op-btn op-btn-secondary" onClick={() => void saveAlternative()} disabled={loading.promote || loading.saveAlt} title={loading.saveAlt ? "Saving alternative…" : undefined}>
                      {loading.saveAlt ? "Saving…" : "Save as alternative"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>

        <Card title="Stored recommendation detail + lineage">
          {!selectedRecommendation ? <EmptyState title="No stored recommendation selected" hint="Select a stored recommendation row to inspect persisted lineage." /> : (() => {
            const p = selectedRecommendation.payload as Record<string, unknown>;
            const catalyst = p.catalyst as Record<string, unknown> | undefined;
            const regime = p.regime as Record<string, unknown> | undefined;
            const entry = p.entry as Record<string, unknown> | undefined;
            const inv = p.invalidation as Record<string, unknown> | undefined;
            const targets = p.targets as Record<string, unknown> | undefined;
            const sizing = p.sizing as Record<string, unknown> | undefined;
            const quality = p.quality as Record<string, unknown> | undefined;
            const sep = { marginTop: 6, paddingTop: 6, borderTop: "1px solid var(--op-border, #1e2d3d)" } as const;
            const label = { fontSize: "0.78rem", color: "var(--op-muted, #7a8999)", marginBottom: 2 } as const;
            return (
              <div className="op-detail-list">
                {/* Header */}
                <div><strong>symbol:</strong> {selectedRecommendation.symbol} &nbsp; <strong>created:</strong> {formatDate(selectedRecommendation.created_at)}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <strong>approved:</strong>
                  {p.approved == null ? <span style={{ color: "var(--op-muted, #7a8999)" }}>—</span> : p.approved ? <StatusBadge tone="good">approved</StatusBadge> : <StatusBadge tone="warn">rejected</StatusBadge>}
                  <button onClick={() => void setApproval(true)} disabled={loading.approve || p.approved === true} style={{ padding: "2px 10px", fontSize: "0.8rem" }}>Approve</button>
                  <button onClick={() => void setApproval(false)} disabled={loading.approve || p.approved === false} style={{ padding: "2px 10px", fontSize: "0.8rem" }}>Reject</button>
                </div>
                <div><strong>source:</strong> {selectedRecommendation.market_data_source ?? "-"}{selectedRecommendation.fallback_mode ? " (fallback)" : ""}</div>

                {/* Thesis */}
                {p.thesis ? <div style={{ paddingTop: 4 }}><strong>thesis:</strong> {asText(p.thesis)}</div> : null}
                {p.rejection_reason ? <div style={{ color: "var(--op-warn, #f2a03f)" }}><strong>rejection reason:</strong> {asText(p.rejection_reason)}</div> : null}

                {/* Catalyst */}
                {catalyst ? (
                  <div style={sep}>
                    <div style={label}>CATALYST</div>
                    <div><strong>type:</strong> {asText(catalyst.type)} &nbsp; <strong>novelty:</strong> {asText(catalyst.novelty)} &nbsp; <strong>source quality:</strong> {asText(catalyst.source_quality)}</div>
                    {catalyst.timestamp ? <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>{String(catalyst.timestamp).slice(0, 19).replace("T", " ")} UTC</div> : null}
                  </div>
                ) : null}

                {/* Regime */}
                {regime ? (
                  <div style={sep}>
                    <div style={label}>REGIME</div>
                    <div>
                      <strong>market:</strong> {asText(regime.market_regime)} &nbsp;
                      <strong>vol:</strong> {asText(regime.volatility_regime)} &nbsp;
                      <strong>breadth:</strong> {asText(regime.breadth_state)}
                    </div>
                  </div>
                ) : null}

                {/* Entry / Stop / Targets */}
                <div style={sep}>
                  <div style={label}>LEVELS</div>
                  {entry ? (
                    <>
                      <div>
                        <strong>entry zone:</strong>{" "}
                        <span style={{ color: "#21c06e" }}>{asText(entry.zone_low ?? entry.low)} – {asText(entry.zone_high ?? entry.high)}</span>
                      </div>
                      {entry.trigger ? <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>trigger: {asText(entry.trigger)}</div> : null}
                    </>
                  ) : null}
                  {inv ? (
                    <div>
                      <strong>stop:</strong>{" "}
                      <span style={{ color: "#f44336" }}>{asText(inv.price)}</span>
                      {inv.reason ? <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}> — {asText(inv.reason)}</span> : null}
                    </div>
                  ) : null}
                  {targets ? (
                    <div>
                      <strong>targets:</strong>{" "}
                      <span style={{ color: "#4caf50" }}>T1 {asText(targets.target_1)}</span>
                      {targets.target_2 != null ? <span style={{ color: "#4caf50" }}> · T2 {asText(targets.target_2)}</span> : null}
                      {targets.trailing_rule ? <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}> ({asText(targets.trailing_rule)})</span> : null}
                    </div>
                  ) : null}
                </div>

                {/* Sizing + Quality */}
                {(sizing ?? quality) ? (
                  <div style={sep}>
                    <div style={label}>SIZING &amp; QUALITY</div>
                    {sizing ? <div><strong>shares:</strong> {asText(sizing.shares)} &nbsp; <strong>risk $:</strong> {asText(sizing.risk_dollars)} &nbsp; <strong>stop dist:</strong> {asText(sizing.stop_distance)}</div> : null}
                    {quality ? <div><strong>expected RR:</strong> {asText(quality.expected_rr)} &nbsp; <strong>confidence:</strong> {asText(quality.confidence)} &nbsp; <strong>risk score:</strong> {asText(quality.risk_score)}</div> : null}
                  </div>
                ) : null}

                {/* Queue lineage */}
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
                  <strong>Queue lineage</strong>
                </div>
                {selectedRecProvenance ? (
                  <>
                    <div><strong>promoted from:</strong> Rank {asText(selectedRecProvenance.rank)} — {asText(selectedRecProvenance.strategy)} on {asText(selectedRecProvenance.symbol)}</div>
                    <div><strong>queue status:</strong> {typeof selectedRecProvenance.status === "string" ? selectedRecProvenance.status.replace(/_/g, " ") : asText(selectedRecProvenance.status)}</div>
                    <div><strong>queue score:</strong> {asText(selectedRecProvenance.score)} &nbsp; <strong>rr:</strong> {asText(selectedRecProvenance.expected_rr)} &nbsp; <strong>conf:</strong> {asText(selectedRecProvenance.confidence)}</div>
                    <div><strong>timeframe:</strong> {asText(selectedRecProvenance.timeframe)} &nbsp; <strong>workflow source:</strong> {asText(selectedRecProvenance.workflow_source)}</div>
                  </>
                ) : (
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>Not promoted from a ranked queue candidate.</div>
                )}
                <div style={{ marginTop: 4 }}><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selectedRecommendation.display_id ?? selectedRecommendation.recommendation_id}</span></div>
              </div>
            );
          })()}
        </Card>
      </div> : null}

      {!isPreviewMode ? <Card title="Chart context (source-matched)">
        <div className="op-row" style={{ marginBottom: 8 }}>
          <StatusBadge tone={fallbackDerived ? "warn" : "good"}>workflow source: {selectedSource}</StatusBadge>
          {fallbackDerived ? <StatusBadge tone="warn">Chart overlays disabled to avoid mixed provider/fallback context.</StatusBadge> : null}
        </div>
        {fallbackDerived ? (
          <EmptyState title="Chart overlays disabled" hint="Selected queue/recommendation was generated from fallback bars, so provider-backed chart overlays stay disabled." />
        ) : (
          <WorkflowChart
            chartPayload={chartPayload}
            storageKey={STORAGE_KEY}
            overlayLevels={chartOverlayLevels}
            emptyTitle="No chart context loaded"
            emptyHint="Select a queue candidate or stored recommendation to inspect the source-matched chart."
            sourceLabel={selectedSource}
          />
        )}
      </Card> : null}
    </section>
  );
}
