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
  getRankingProvenance,
  isFallbackWorkflow,
  parseRecommendationSearchParams,
  type QueueCandidate,
  type StoredRecommendation,
} from "@/lib/recommendations";

const STORAGE_KEY = "macmarket-indicators-recommendations";

function asText(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export default function RecommendationsPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const searchParams = useSearchParams();
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);

  const [rows, setRows] = useState<StoredRecommendation[]>([]);
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [selectedQueueKey, setSelectedQueueKey] = useState<string | null>(null);
  const [selectedRecommendationId, setSelectedRecommendationId] = useState<number | null>(null);
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA,AMZN");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState({ queue: false, recommendations: false, promote: false });
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
    const result = await fetchWorkflowApi<{ queue: QueueCandidate[] }>("/api/user/recommendations/queue", {
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
    async function renderChart() {
      const chartSymbol = selectedRecommendation?.symbol ?? selectedQueue?.symbol;
      const timeframe = selectedQueue?.timeframe ?? "1D";
      if (!chartRef.current || !chartSymbol || fallbackDerived) return;
      const payload = await fetchHacoChart({ symbol: chartSymbol, timeframe, include_heikin_ashi: false });
      if (chartApiRef.current) chartApiRef.current.remove();
      const chart = createChart(chartRef.current, { height: 320, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      chartApiRef.current = chart;
      const candles: Array<CandlestickData<Time> & { volume: number }> = payload.candles
        .slice(-120)
        .map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume }));
      chart.addCandlestickSeries().setData(candles);
      applyIndicatorsToChart(chart, candles, selectedIndicators);
    }
    void renderChart();
    return () => chartApiRef.current?.remove();
  }, [selectedQueue?.symbol, selectedQueue?.timeframe, selectedRecommendation?.symbol, fallbackDerived, selectedIndicators]);

  const selectedRecProvenance = getRankingProvenance((selectedRecommendation?.payload as Record<string, unknown>) ?? null);

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
          {loading.queue && queue.length === 0 ? <EmptyState title="Loading queue" hint="Fetching ranked queue candidates." /> : null}
          {!loading.queue && queue.length === 0 ? <EmptyState title="No queue candidates" hint="Refresh queue with at least one symbol." /> : null}
          {queue.length > 0 ? (
            <table className="op-table">
              <thead><tr><th>rank</th><th>symbol</th><th>strategy</th><th>source</th><th>status</th><th>score</th></tr></thead>
              <tbody>
                {queue.map((row) => {
                  const key = `${row.symbol}-${row.strategy}-${row.rank}`;
                  return (
                    <tr key={key} className={`is-selectable ${selectedQueueKey === key ? "is-active" : ""}`} onClick={() => { setSelectedQueueKey(key); setSelectedRecommendationId(null); }}>
                      <td>{row.rank}</td><td>{row.symbol}</td><td>{row.strategy}</td><td>{row.workflow_source}</td><td>{row.status}</td><td>{row.score}</td>
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
              <thead><tr><th>created</th><th>symbol</th><th>recommendation id</th><th>approved</th><th>source</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className={`is-selectable ${selectedRecommendationId === row.id ? "is-active" : ""}`} onClick={() => { setSelectedRecommendationId(row.id); setSelectedQueueKey(null); }}>
                    <td>{row.created_at}</td>
                    <td>{row.symbol}</td>
                    <td>{row.recommendation_id}</td>
                    <td>{String((row.payload as Record<string, unknown>)?.approved ?? "-")}</td>
                    <td>{row.market_data_source ?? asText((row.payload.workflow as Record<string, unknown> | undefined)?.market_data_source)}</td>
                  </tr>
                ))}
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
              <div><strong>source/workflow_source:</strong> {selectedQueue.source ?? "-"} / {selectedQueue.workflow_source}</div>
              <div><strong>status:</strong> {selectedQueue.status}</div>
              <div><strong>score:</strong> {selectedQueue.score}</div>
              <div><strong>score_breakdown:</strong> {asText(selectedQueue.score_breakdown)}</div>
              <div><strong>expected_rr:</strong> {selectedQueue.expected_rr}</div>
              <div><strong>confidence:</strong> {selectedQueue.confidence}</div>
              <div><strong>thesis:</strong> {selectedQueue.thesis}</div>
              <div><strong>trigger:</strong> {asText(selectedQueue.trigger)}</div>
              <div><strong>entry_zone:</strong> {asText(selectedQueue.entry_zone)}</div>
              <div><strong>invalidation:</strong> {asText(selectedQueue.invalidation)}</div>
              <div><strong>targets:</strong> {asText(selectedQueue.targets)}</div>
              <div><strong>reason_text:</strong> {selectedQueue.reason_text}</div>
            </div>
          )}
        </Card>

        <Card title="Stored recommendation detail + lineage">
          {!selectedRecommendation ? <EmptyState title="No stored recommendation selected" hint="Select a stored recommendation row to inspect persisted lineage." /> : (
            <div className="op-detail-list">
              <div><strong>recommendation id:</strong> {selectedRecommendation.recommendation_id}</div>
              <div><strong>symbol:</strong> {selectedRecommendation.symbol}</div>
              <div><strong>created_at:</strong> {selectedRecommendation.created_at}</div>
              <div><strong>approved:</strong> {String((selectedRecommendation.payload as Record<string, unknown>)?.approved ?? "-")}</div>
              <div><strong>workflow source metadata:</strong> {selectedRecommendation.market_data_source ?? "-"} / fallback={String(selectedRecommendation.fallback_mode ?? false)}</div>
              <div><strong>thesis:</strong> {asText((selectedRecommendation.payload as Record<string, unknown>)?.thesis)}</div>
              <div><strong>entry:</strong> {asText((selectedRecommendation.payload as Record<string, unknown>)?.entry)}</div>
              <div><strong>invalidation:</strong> {asText((selectedRecommendation.payload as Record<string, unknown>)?.invalidation)}</div>
              <div><strong>targets:</strong> {asText((selectedRecommendation.payload as Record<string, unknown>)?.targets)}</div>
              <div><strong>ranking provenance:</strong> {asText(selectedRecProvenance)}</div>
              <div><strong>origin queue relationship:</strong> {selectedRecProvenance ? `Promoted from rank ${asText(selectedRecProvenance.rank)} (${asText(selectedRecProvenance.strategy)} on ${asText(selectedRecProvenance.symbol)})` : "No queue promotion provenance persisted."}</div>
            </div>
          )}
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
