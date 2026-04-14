"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, parseGuidedFlowState } from "@/lib/guided-workflow";
import { WorkflowBanner } from "@/components/workflow-banner";

type Order = { order_id: string; recommendation_id: string; symbol: string; status: string; side: string; shares: number; limit_price: number; created_at: string; market_data_source?: string | null; fallback_mode?: boolean | null; fills: Array<{ fill_price: number; filled_shares: number; timestamp: string }> };

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
  const [explainerDismissed, setExplainerDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("macmarket-orders-explainer-dismissed") === "1";
  });
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const selected = useMemo(() => orders.find((o) => o.order_id === selectedOrderId) ?? null, [orders, selectedOrderId]);
  const unsupportedGuidedMode = Boolean(guidedState.guided && guidedState.marketMode && guidedState.marketMode !== "equities");

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
      if (result.authPending) {
        setError(null);
        setFeedback({ state: "loading", message: "Authentication initializing. Retrying shortly…" });
        setBusy(false);
        return;
      }
      const message = result.status === 503
        ? "Configured provider unavailable. Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Orders load failed.");
      setError(message);
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }
    setError(null);
    setFeedback({ state: "success", message: "Orders updated." });
    setOrders(result.items);
    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    const requestedOrder = new URLSearchParams(searchKey).get("order");
    setSelectedOrderId((prev) => prev
      ?? result.items.find((order) => order.order_id === requestedOrder)?.order_id
      ?? result.items.find((order) => order.recommendation_id === requestedRecommendation)?.order_id
      ?? result.items[0]?.order_id
      ?? null);
    setDataSource((result.items[0]?.fallback_mode ? `fallback (${result.items[0]?.market_data_source ?? "provider"})` : (result.items[0]?.market_data_source ?? "provider")) ?? "workflow pending");
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
    // Use the selected order's symbol if available, or fall back to the recommendation's symbol from query param.
    // Never hardcode AAPL when a recommendation context is present.
    const symbolHint = selected?.symbol ?? guidedState.symbol ?? null;
    const body: Record<string, unknown> = {};
    if (requestedRecommendation) {
      body.recommendation_id = requestedRecommendation;
    } else if (symbolHint) {
      body.symbol = symbolHint;
    } else {
      body.symbol = "AAPL";
    }
    body.market_mode = guidedState.marketMode ?? "equities";
    if (guidedState.guided) {
      body.guided = true;
      if (guidedState.replayRunId) body.replay_run_id = Number(guidedState.replayRunId);
    }
    const result = await fetchWorkflowApi<{ order_id: string; market_data_source?: string; fallback_mode?: boolean }>(
      "/api/user/orders",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    );
    if (!result.ok) {
      if (result.authPending) {
        setFeedback({ state: "loading", message: "Authentication initializing. Retry in a moment." });
        setBusy(false);
        return;
      }
      const message = result.status === 503
        ? "Configured provider unavailable. Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Unable to stage order.");
      setError(message);
      setStatus("failed");
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }
    setError(null);
    const fallbackMode = result.data?.fallback_mode ?? false;
    const sourceName = result.data?.market_data_source ?? "provider";
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    if (result.data?.order_id) {
      setSelectedOrderId(result.data.order_id);
      const query = buildGuidedQuery({
        guided: guidedState.guided,
        symbol: selected?.symbol ?? guidedState.symbol,
        strategy: guidedState.strategy,
        recommendationId: requestedRecommendation ?? guidedState.recommendationId,
        replayRunId: guidedState.replayRunId,
        source: dataSource,
        orderId: result.data.order_id,
      });
      router.replace(`/orders?${query}`);
    }
    setStatus("paper order staged");
    setFeedback({ state: "success", message: "Paper order staged." });
    await load();
    setBusy(false);
  }

  useEffect(() => {
    if (!authReady) return;
    void load();
  }, [searchKey, isLoaded, isSignedIn]);
  useEffect(() => {
    if (feedback.state !== "success") return;
    const timer = window.setTimeout(() => setFeedback({ state: "idle", message: "" }), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback.state, feedback.message]);

  return <section className="op-stack">
    <PageHeader title="Orders blotter" subtitle="Paper/dev execution only. No live trading route is exposed." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <WorkflowBanner
      current="Paper Order"
      state={{
        ...guidedState,
        symbol: selected?.symbol ?? guidedState.symbol,
        source: dataSource,
        orderId: selected?.order_id ?? guidedState.orderId,
      }}
      backHref="/replay-runs"
      backLabel="Back to Replay"
      compact={!guidedState.guided}
    />
    {guidedState.guided ? (
      <Card title="Guided flow progress">
        <GuidedStepRail current="Paper Order" />
      </Card>
    ) : null}
    {guidedState.guided ? (
      <Card title="Next action">
        <div>Review the staged paper order and confirm linkage to the recommendation + replay lineage before any further routing decisions.</div>
        {unsupportedGuidedMode ? <ErrorState title="Research preview mode" hint="Options and crypto remain research preview only. Guided execution-prep is disabled." /> : null}
        <div className="op-row" style={{ marginTop: 8 }}>
          <button onClick={() => selected?.order_id && setSelectedOrderId(selected.order_id)} disabled={!selected}>Review staged paper order</button>
        </div>
      </Card>
    ) : null}
    {!explainerDismissed && (
      <Card title="Paper Trading Blotter">
        <p style={{margin: "0 0 8px 0"}}>
          Paper orders are <strong>simulated</strong> — no real money is involved. This is the final step in the workflow before you would consider a live trade.
        </p>
        <p style={{margin: "0 0 8px 0"}}>
          Review the order ticket carefully: check the symbol, side, shares, limit price, stop, and targets match your recommendation before staging.
        </p>
        <button
          onClick={() => {
            localStorage.setItem("macmarket-orders-explainer-dismissed", "1");
            setExplainerDismissed(true);
          }}
          className="op-btn op-btn-ghost"
        >
          Got it, don&apos;t show again
        </button>
      </Card>
    )}
    <Card title="Blotter mode">
      Generated from recommendation workflow bars sourced from: <strong>{dataSource}</strong>. This is paper-only execution for operator review.
    </Card>
    <Card title="What a good blotter review looks like">
      Confirm the staged order maps to the intended recommendation, source mode, and deterministic sizing before considering live-route promotion.
    </Card>
    {!authReady ? <Card title="Auth status">Initializing authenticated session before orders API requests.</Card> : null}
    <Card>
      <div className="op-row">
        <button onClick={() => void stagePaperOrder()} disabled={busy || unsupportedGuidedMode}>{busy ? "Staging..." : "Stage Simulated Paper Order (no real money)"}</button>
        <button onClick={() => void load()} disabled={busy}>{busy ? "Refreshing..." : "Refresh blotter"}</button>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
    </Card>
    {error ? <ErrorState title="Orders unavailable" hint={error} /> : null}
    {orders.length === 0 && !error ? (
      <div className="op-stack">
        <EmptyState title="No orders yet" hint="Run replay first, then click 'Stage Simulated Paper Order'. Paper orders are simulated — no real money is involved." />
        <div><a href="/replay-runs" className="op-btn op-btn-primary" style={{ display: "inline-flex" }}>→ Go to Replay</a></div>
      </div>
    ) : null}
    <div className="op-grid-2">
      <Card title="Order table">
        <table className="op-table">
          <thead><tr><th>created_at</th><th>symbol</th><th>side</th><th>shares</th><th>limit/fill</th><th>broker status</th><th>fill count</th></tr></thead>
          <tbody>{orders.map((o) => <tr key={o.order_id} onClick={() => setSelectedOrderId(o.order_id)} className={`is-selectable ${selectedOrderId === o.order_id ? "is-active" : ""}`}><td>{o.created_at}</td><td>{o.symbol}</td><td><StatusBadge tone={o.side === "buy" ? "good" : "warn"}>{o.side}</StatusBadge></td><td>{o.shares}</td><td>{o.limit_price} / {o.fills[0]?.fill_price ?? "-"}</td><td><StatusBadge tone={o.status.includes("fill") ? "good" : "warn"}>{o.status}</StatusBadge></td><td>{o.fills.length}</td></tr>)}</tbody>
        </table>
      </Card>
      <Card title="Selected order detail">
        {guidedState.guided ? <div className="op-row" style={{ marginBottom: 8 }}><button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button></div> : null}
        {!selected ? <EmptyState title="Select an order" hint="Click a blotter row to inspect paper-broker fill details." /> : <div style={{ display: "grid", gap: 6 }}>
          <div><strong>Order id:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selected.order_id}</span></div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <strong>Recommendation:</strong>
            {selected.recommendation_id
              ? <a href={`/recommendations?recommendation=${encodeURIComponent(selected.recommendation_id)}`} style={{ color: "var(--op-accent, #4d8dff)", fontFamily: "monospace", fontSize: "0.8rem" }}>{selected.recommendation_id}</a>
              : <span style={{ color: "var(--op-muted, #7a8999)" }}>pending linkage</span>
            }
          </div>
          <div><strong>Why this paper order exists:</strong> staged from approved recommendation path for operator verification before any live-route discussion.</div>
          {!guidedState.guided || showOperatorDetail ? (
            <>
              <div><strong>Symbol/side:</strong> {selected.symbol} {selected.side}</div>
              <div><strong>Shares:</strong> {selected.shares}</div>
              <div><strong>Limit:</strong> {selected.limit_price}</div>
              <div><strong>Status:</strong> {selected.status}</div>
              <div><strong>Workflow source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)}</div>
              <div><strong>Created at:</strong> {selected.created_at}</div>
              <div><strong>Fills:</strong></div>
              {selected.fills.map((fill, idx) => <div key={idx}>#{idx + 1} {fill.filled_shares} @ {fill.fill_price} ({fill.timestamp})</div>)}
            </>
          ) : (
            <div style={{ color: "var(--op-muted, #7a8999)" }}>Advanced operator fields are collapsed in guided mode.</div>
          )}
        </div>}
      </Card>
    </div>
  </section>;
}
