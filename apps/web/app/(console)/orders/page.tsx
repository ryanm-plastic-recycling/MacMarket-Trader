"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, parseGuidedFlowState } from "@/lib/guided-workflow";
import { WorkflowBanner } from "@/components/workflow-banner";
import { pickOrderSelection } from "@/lib/workflow-selection";

type Order = { order_id: string; recommendation_id: string; replay_run_id?: number | null; symbol: string; status: string; side: string; shares: number; limit_price: number; created_at: string; market_data_source?: string | null; fallback_mode?: boolean | null; fills: Array<{ fill_price: number; filled_shares: number; timestamp: string }> };
type PortfolioSummary = { open_positions: number; total_open_notional: number; unrealized_pnl: number; realized_pnl: number; closed_trade_count: number; win_rate: number; lifecycle_status?: string; notes?: string };

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const guidedState = useMemo(() => parseGuidedFlowState(searchParams), [searchParams]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("workflow pending");
  const [busy, setBusy] = useState(false);
  const [showOperatorDetail, setShowOperatorDetail] = useState(false);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);
  const [replayOutcome, setReplayOutcome] = useState<{ has_stageable_candidate: boolean; stageable_reason?: string | null } | null>(null);
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const selected = useMemo(() => orders.find((o) => o.order_id === selectedOrderId) ?? null, [orders, selectedOrderId]);
  const unsupportedGuidedMode = Boolean(guidedState.guided && guidedState.marketMode && guidedState.marketMode !== "equities");
  const detailRef = useRef<HTMLDivElement | null>(null);

  async function load() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Initializing authenticated workflow…" });
      return;
    }
    setBusy(true);
    setError(null);
    setFeedback({ state: "loading", message: "Loading orders…" });
    const result = await fetchWorkflowApi<Order>("/api/user/orders");
    if (!result.ok) {
      const message = result.status === 503
        ? "Configured provider unavailable. Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Orders load failed.");
      setError(message);
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }

    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    const requestedOrder = new URLSearchParams(searchKey).get("order");
    const requestedReplayRun = new URLSearchParams(searchKey).get("replay_run");
    setOrders(result.items);
    setSelectedOrderId((prev) => prev ?? pickOrderSelection({
      guided: guidedState.guided,
      requestedOrderId: requestedOrder,
      requestedReplayRunId: requestedReplayRun,
      requestedRecommendationId: requestedRecommendation,
      orders: result.items,
    }));
    const firstSource = result.items[0]?.fallback_mode ? `fallback (${result.items[0]?.market_data_source ?? "provider"})` : (result.items[0]?.market_data_source ?? "provider");
    setDataSource(firstSource ?? "workflow pending");
    setFeedback({ state: "success", message: "Orders updated." });
    const summary = await fetchWorkflowApi<PortfolioSummary>("/api/user/orders/portfolio-summary");
    if (summary.ok) setPortfolioSummary(summary.data ?? null);
    setBusy(false);
  }

  async function stagePaperOrder() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Authentication still initializing." });
      return;
    }
    setStatus("staging paper order...");
    setBusy(true);
    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    const symbolHint = selected?.symbol ?? guidedState.symbol ?? null;
    const body: Record<string, unknown> = {};
    if (guidedState.guided && !requestedRecommendation) {
      setError("Guided order staging requires recommendation lineage.");
      setBusy(false);
      return;
    }
    if (requestedRecommendation) body.recommendation_id = requestedRecommendation;
    else if (symbolHint) body.symbol = symbolHint;
    else {
      setError("Provide symbol context for non-guided order staging.");
      setBusy(false);
      return;
    }

    body.market_mode = guidedState.marketMode ?? "equities";
    if (guidedState.guided) {
      body.guided = true;
      if (guidedState.replayRunId) body.replay_run_id = Number(guidedState.replayRunId);
    }

    const result = await fetchWorkflowApi<{ order_id: string; market_data_source?: string; fallback_mode?: boolean; recommendation_id?: string; replay_run_id?: number; symbol?: string; side?: string; shares?: number; limit_price?: number; status?: string }>(
      "/api/user/orders",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    );
    if (!result.ok) {
      const message = result.status === 503
        ? "Configured provider unavailable. Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Unable to stage order.");
      setError(message);
      setStatus("failed");
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }

    const fallbackMode = result.data?.fallback_mode ?? false;
    const sourceName = result.data?.market_data_source ?? "provider";
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);

    if (result.data?.order_id) {
      const hydrated: Order = {
        order_id: result.data.order_id,
        recommendation_id: result.data.recommendation_id ?? requestedRecommendation ?? guidedState.recommendationId ?? "",
        replay_run_id: result.data.replay_run_id ?? (guidedState.replayRunId ? Number(guidedState.replayRunId) : null),
        symbol: result.data.symbol ?? symbolHint ?? "—",
        side: result.data.side ?? "buy",
        shares: result.data.shares ?? 0,
        limit_price: result.data.limit_price ?? 0,
        status: result.data.status ?? "staged",
        created_at: new Date().toISOString(),
        market_data_source: sourceName,
        fallback_mode: fallbackMode,
        fills: [],
      };
      setOrders((prev) => [hydrated, ...prev.filter((item) => item.order_id !== hydrated.order_id)]);
      setSelectedOrderId(result.data.order_id);
      const query = buildGuidedQuery({
        guided: guidedState.guided,
        symbol: hydrated.symbol,
        strategy: guidedState.strategy,
        recommendationId: hydrated.recommendation_id,
        replayRunId: hydrated.replay_run_id != null ? String(hydrated.replay_run_id) : guidedState.replayRunId,
        source: sourceName,
        orderId: result.data.order_id,
      });
      router.replace(`/orders?${query}`);
    }

    setStatus("paper order staged");
    setFeedback({ state: "success", message: "Paper order staged." });
    await load();
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setBusy(false);
  }

  useEffect(() => {
    if (!authReady) return;
    void load();
  }, [searchKey, authReady]);

  useEffect(() => {
    if (!authReady || !guidedState.replayRunId) return;
    void (async () => {
      const result = await fetchWorkflowApi<{ has_stageable_candidate: boolean; stageable_reason?: string | null }>(
        `/api/user/replay-runs/${guidedState.replayRunId}`,
      );
      if (result.ok) setReplayOutcome(result.data ?? null);
    })();
  }, [authReady, guidedState.replayRunId]);

  useEffect(() => {
    if (!selectedOrderId) return;
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selectedOrderId]);

  return <section className="op-stack">
    <PageHeader title="Paper Orders" subtitle="Step 4 action page: stage deterministic paper orders from replay lineage." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <WorkflowBanner
      current="Paper Order"
      state={{
        ...guidedState,
        symbol: selected?.symbol ?? guidedState.symbol,
        source: selected?.market_data_source ?? dataSource,
        recommendationId: selected?.recommendation_id ?? guidedState.recommendationId,
        replayRunId: selected?.replay_run_id != null ? String(selected.replay_run_id) : guidedState.replayRunId,
        orderId: selected?.order_id ?? guidedState.orderId,
      }}
      backHref="/replay-runs"
      backLabel="Back to Replay"
      nextDisabled={guidedState.guided && (!guidedState.recommendationId || !guidedState.replayRunId)}
      nextDisabledReason="Guided paper orders require both recommendation and replay lineage."
      compact={!guidedState.guided}
    />
    {guidedState.guided ? <Card title="Guided flow progress"><GuidedStepRail current="Paper Order" /></Card> : null}
    {portfolioSummary ? (
      <Card title="Paper portfolio summary">
        <div className="op-row" style={{ flexWrap: "wrap", gap: 12 }}>
          <span>Open positions: <strong>{portfolioSummary.open_positions}</strong></span>
          <span>Open notional: <strong>{portfolioSummary.total_open_notional.toFixed(2)}</strong></span>
          <span>Unrealized P&L: <strong>{portfolioSummary.unrealized_pnl.toFixed(2)}</strong></span>
          <span>Realized P&L: <strong>{portfolioSummary.realized_pnl.toFixed(2)}</strong></span>
          <span>Closed trades: <strong>{portfolioSummary.closed_trade_count}</strong></span>
          <span>Win rate: <strong>{(portfolioSummary.win_rate * 100).toFixed(1)}%</strong></span>
        </div>
        {portfolioSummary.notes ? <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)" }}>{portfolioSummary.notes}</div> : null}
      </Card>
    ) : null}

    <Card title="What orders are for">
      Stage a paper order from replay-backed recommendation context before any live-route discussion.
      <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)" }}>Arriving here does not stage an order.</div>
    </Card>
    <Card title="Workflow lineage">
      <div><strong>recommendation:</strong> {selected?.recommendation_id ?? guidedState.recommendationId ?? "—"} → <strong>replay run:</strong> {selected?.replay_run_id ?? guidedState.replayRunId ?? "—"} → <strong>paper order:</strong> {selected?.order_id ?? guidedState.orderId ?? "—"}</div>
    </Card>

    {guidedState.guided ? (
      <Card title="Paper order ticket">
        {!selected ? (
          <div className="op-card" style={{ padding: 12 }}>
            <h3 style={{ margin: "0 0 6px 0" }}>No paper order staged yet</h3>
            <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{guidedState.recommendationId ?? "—"}</span></div>
            <div><strong>replay run id:</strong> <span style={{ fontFamily: "monospace" }}>{guidedState.replayRunId ?? "—"}</span></div>
            <div><strong>symbol:</strong> {guidedState.symbol ?? "—"} · <strong>strategy:</strong> {guidedState.strategy ?? "—"}</div>
            <button style={{ marginTop: 8, width: "100%" }} onClick={() => void stagePaperOrder()} disabled={busy || unsupportedGuidedMode || replayOutcome?.has_stageable_candidate === false}>{busy ? "Staging..." : "Stage paper order now"}</button>
            {replayOutcome?.has_stageable_candidate === false ? <div style={{ marginTop: 6, color: "var(--op-warn, #f2a03f)" }}>No paper order can be staged from this replay. {replayOutcome.stageable_reason ?? ""}</div> : null}
          </div>
        ) : (
          <>
            <div><strong>symbol:</strong> {selected.symbol} · <strong>side:</strong> {selected.side} · <strong>shares:</strong> {selected.shares} · <strong>limit:</strong> {selected.limit_price}</div>
            <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{selected.recommendation_id}</span> · <strong>replay run id:</strong> <span style={{ fontFamily: "monospace" }}>{selected.replay_run_id ?? "—"}</span></div>
            <div><strong>source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)} · <strong>status:</strong> {selected.status}</div>
          </>
        )}
      </Card>
    ) : null}

    <Card><div className="op-row"><button onClick={() => void stagePaperOrder()} disabled={busy || unsupportedGuidedMode || replayOutcome?.has_stageable_candidate === false}>{busy ? "Staging..." : "Stage paper order now"}</button><button onClick={() => void load()} disabled={busy}>{busy ? "Refreshing..." : "Refresh order history"}</button></div><InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} /></Card>
    {error ? <ErrorState title="Orders unavailable" hint={error} /> : null}

    <div className="op-grid-2">
      <Card title={guidedState.guided ? "Order history (secondary)" : "Order history"}>
        {guidedState.guided ? <div style={{ marginBottom: 6, color: "var(--op-muted, #7a8999)" }}>Secondary panel: full order history</div> : null}
        <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
        <table className="op-table" style={{ marginTop: guidedState.guided ? 8 : 0 }}>
          <thead><tr><th>created_at</th><th>symbol</th><th>side</th><th>shares</th><th>limit/fill</th><th>broker status</th><th>fill count</th></tr></thead>
          <tbody>{orders.map((o) => <tr key={o.order_id} onClick={() => setSelectedOrderId(o.order_id)} className={`is-selectable ${selectedOrderId === o.order_id ? "is-active" : ""}`}><td>{o.created_at}</td><td>{o.symbol}</td><td><StatusBadge tone={o.side === "buy" ? "good" : "warn"}>{o.side}</StatusBadge></td><td>{o.shares}</td><td>{o.limit_price} / {o.fills[0]?.fill_price ?? "-"}</td><td><StatusBadge tone={o.status.includes("fill") ? "good" : "warn"}>{o.status}</StatusBadge></td><td>{o.fills.length}</td></tr>)}</tbody>
        </table>
        </div>
      </Card>
      <Card title="Selected order detail">
        {guidedState.guided ? <div className="op-row" style={{ marginBottom: 8 }}><button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button></div> : null}
        <div ref={detailRef}>
          {!selected ? <EmptyState title="Select an order" hint="Click a blotter row to inspect paper-broker fill details." /> : <div style={{ display: "grid", gap: 6 }}>
            <div><strong>Order id:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selected.order_id}</span></div>
            <div><strong>Recommendation:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selected.recommendation_id}</span></div>
            <div><strong>Replay run:</strong> {selected.replay_run_id ?? "—"}</div>
            <div><strong>Symbol/side:</strong> {selected.symbol} {selected.side}</div>
            <div><strong>Shares:</strong> {selected.shares}</div>
            <div><strong>Limit:</strong> {selected.limit_price}</div>
            <div><strong>Status:</strong> {selected.status}</div>
            <div><strong>Workflow source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)}</div>
            {(!guidedState.guided || showOperatorDetail) ? <><div><strong>Created at:</strong> {selected.created_at}</div><div><strong>Fills:</strong></div>{selected.fills.map((fill, idx) => <div key={idx}>#{idx + 1} {fill.filled_shares} @ {fill.fill_price} ({fill.timestamp})</div>)}</> : null}
          </div>}
        </div>
      </Card>
    </div>
  </section>;
}
