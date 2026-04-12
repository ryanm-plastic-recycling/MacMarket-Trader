"use client";

import { createChart, type CandlestickData, type IChartApi, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { fetchHacoChart } from "@/lib/haco-api";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS } from "@/lib/chart-indicators";
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
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  const [rows, setRows] = useState<StoredRecommendation[]>([]);
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [queueSummary, setQueueSummary] = useState<QueueSummary | null>(null);
  const [selectedQueueKey, setSelectedQueueKey] = useState<string | null>(null);
  const [selectedRecommendationId, setSelectedRecommendationId] = useState<number | null>(null);
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA,AMZN");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState({ queue: false, recommendations: false, promote: false, approve: false });
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);

  const prefill = useMemo(() => parseRecommendationSearchParams(searchParams), [searchParams]);

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
      body: JSON.stringify(selectedQueue),
    });
    setLoading((prev) => ({ ...prev, promote: false }));

    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Promotion failed" });
      return;
    }

    setError(null);
    setFeedback({ state: "success", message: "Queue candidate promoted to stored recommendation." });
    const promotedRecommendationId = result.data?.recommendation_id;
    await loadRecommendations({ selectRecommendationUid: promotedRecommendationId });
  }

  function openReplay() {
    if (selectedRecommendation?.recommendation_id) {
      window.location.assign(`/replay-runs?symbol=${selectedRecommendation.symbol}&recommendation=${selectedRecommendation.recommendation_id}`);
      return;
    }
    if (selectedQueue) {
      window.location.assign(`/replay-runs?symbol=${selectedQueue.symbol}`);
    }
  }

  function openOrders() {
    if (selectedRecommendation?.recommendation_id) {
      window.location.assign(`/orders?recommendation=${selectedRecommendation.recommendation_id}`);
      return;
    }
    if (selectedQueue) {
      window.location.assign(`/orders?symbol=${selectedQueue.symbol}`);
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
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    try {
      setSelectedIndicators(normalizeSelection(raw ? (JSON.parse(raw) as string[]) : []).filter((item) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(item)));
    } catch {
      setSelectedIndicators(["ema20", "vwap", "prior_day_levels"]);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedIndicators));
  }, [selectedIndicators]);

  useEffect(() => {
    let cancelled = false;
    async function renderChart() {
      const chartSymbol = selectedRecommendation?.symbol ?? selectedQueue?.symbol;
      const timeframe = selectedQueue?.timeframe ?? "1D";
      if (!chartRef.current || !chartSymbol || fallbackDerived) return;
      const payload = await fetchHacoChart({ symbol: chartSymbol, timeframe, include_heikin_ashi: false });
      // If the effect was cleaned up while fetchHacoChart was in flight, bail out
      // before touching the chart ref — it may already be disposed by the cleanup.
      if (cancelled) return;
      if (chartApiRef.current) {
        chartApiRef.current.remove();
        chartApiRef.current = null;
      }
      const chart = createChart(chartRef.current, { height: 320, autoSize: true, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      chartApiRef.current = chart;
      const candles: Array<CandlestickData<Time> & { volume: number }> = payload.candles
        .slice(-120)
        .map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume }));
      const priceSeries = chart.addCandlestickSeries();
      priceSeries.setData(candles);
      applyIndicatorsToChart(chart, candles, selectedIndicators);

      // Overlay entry zone, stop, and target price lines from current selection
      const levels = extractLevels(selectedRecommendation, selectedQueue);
      if (levels.entryLow != null) priceSeries.createPriceLine({ price: levels.entryLow, color: "#21c06e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "entry low" });
      if (levels.entryHigh != null) priceSeries.createPriceLine({ price: levels.entryHigh, color: "#21c06e", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "entry high" });
      if (levels.stop != null) priceSeries.createPriceLine({ price: levels.stop, color: "#f44336", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: "stop" });
      if (levels.target1 != null) priceSeries.createPriceLine({ price: levels.target1, color: "#4caf50", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "T1" });
      if (levels.target2 != null) priceSeries.createPriceLine({ price: levels.target2, color: "#4caf50", lineWidth: 1, lineStyle: 1, axisLabelVisible: true, title: "T2" });

      chart.timeScale().fitContent();
    }
    void renderChart();
    return () => {
      cancelled = true;
      if (chartApiRef.current) {
        chartApiRef.current.remove();
        chartApiRef.current = null;
      }
    };
  }, [selectedQueue?.symbol, selectedQueue?.timeframe, selectedRecommendation?.symbol, selectedRecommendation?.id, selectedQueueKey, fallbackDerived, selectedIndicators]);

  const selectedRecProvenance = getRankingProvenance((selectedRecommendation?.payload as Record<string, unknown>) ?? null);
  const promotedKeys = useMemo(() => getPromotedQueueKeys(rows), [rows]);

  return (
    <section className="op-stack">
      <PageHeader
        title="Recommendations"
        subtitle="Flagship review workspace for ranked queue candidates and persisted recommendation lineage."
        actions={<StatusBadge tone={fallbackDerived ? "warn" : "neutral"}>{fallbackDerived ? "Fallback workflow context" : "Provider workflow context"}</StatusBadge>}
      />

      <Card>
        <div className="op-row">
          <input value={symbols} onChange={(e) => setSymbols(e.target.value.toUpperCase())} style={{ minWidth: 320 }} placeholder="AAPL,MSFT,NVDA" />
          <button onClick={() => void loadQueue()} disabled={loading.queue}>Refresh queue</button>
          <button onClick={() => void promoteSelected()} disabled={!selectedQueue || loading.promote}>{loading.promote ? "Promoting…" : "Promote selected queue candidate"}</button>
          <button onClick={openReplay} disabled={!selectedQueue && !selectedRecommendation}>Open Replay</button>
          <button onClick={openOrders} disabled={!selectedQueue && !selectedRecommendation}>Open Orders</button>
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadQueue()} />
      </Card>

      {error ? <ErrorState title="Recommendations workflow unavailable" hint={error} /> : null}

      <div className="op-grid-2">
        <Card title="Ranked queue candidates">
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
        </Card>

        <Card title="Persisted recommendations">
          {loading.recommendations && rows.length === 0 ? <EmptyState title="Loading recommendations" hint="Fetching stored recommendations." /> : null}
          {!loading.recommendations && rows.length === 0 ? <EmptyState title="No stored recommendations" hint="Promote a queue candidate to create reviewable lineage." /> : null}
          {rows.length > 0 ? (
            <table className="op-table">
              <thead><tr><th>date</th><th>symbol</th><th>strategy</th><th>queue rank</th><th>approved</th><th>source</th></tr></thead>
              <tbody>
                {rows.map((row) => {
                  const prov = getRankingProvenance(row.payload as Record<string, unknown>);
                  const strategy = typeof prov?.strategy === "string" ? prov.strategy : "-";
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
          ) : null}
        </Card>
      </div>

      <div className="op-grid-2">
        <Card title="Queue candidate detail">
          {!selectedQueue ? <EmptyState title="No queue selection" hint="Select a queue row to review deterministic ranking detail." /> : (
            <div className="op-detail-list">
              <div><strong>rank:</strong> {selectedQueue.rank}</div>
              <div><strong>symbol:</strong> {selectedQueue.symbol}</div>
              <div><strong>strategy:</strong> {selectedQueue.strategy}</div>
              <div><strong>timeframe:</strong> {selectedQueue.timeframe}</div>
              <div><strong>market_mode:</strong> {selectedQueue.market_mode ?? "equities"}</div>
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
              <div style={{ marginTop: 12, paddingTop: 8, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
                {promotedKeys.has(`${selectedQueue.symbol}-${selectedQueue.strategy}-${selectedQueue.rank}`) ? (
                  <StatusBadge tone="good">Already promoted to recommendation</StatusBadge>
                ) : (
                  <button onClick={() => void promoteSelected()} disabled={loading.promote} style={{ width: "100%" }}>
                    {loading.promote ? "Promoting…" : "Promote to recommendation"}
                  </button>
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
                <div style={{ marginTop: 4 }}><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selectedRecommendation.recommendation_id}</span></div>
              </div>
            );
          })()}
        </Card>
      </div>

      <Card title="Chart context (source-matched)">
        <div className="op-row" style={{ marginBottom: 8 }}>
          <StatusBadge tone={fallbackDerived ? "warn" : "good"}>workflow source: {selectedSource}</StatusBadge>
          {fallbackDerived ? <StatusBadge tone="warn">Chart overlays disabled to avoid mixed provider/fallback context.</StatusBadge> : null}
        </div>
        <IndicatorSelector selected={selectedIndicators} onChange={setSelectedIndicators} enabledIds={FIRST_CLASS_WORKFLOW_INDICATORS} />
        {fallbackDerived ? <EmptyState title="Chart overlays disabled" hint="Selected queue/recommendation was generated from fallback bars, so provider-backed chart overlays stay disabled." /> : <div ref={chartRef} />}
      </Card>
    </section>
  );
}
