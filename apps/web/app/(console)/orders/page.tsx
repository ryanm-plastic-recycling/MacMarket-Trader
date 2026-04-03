"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type Order = { order_id: string; recommendation_id: string; symbol: string; status: string; side: string; shares: number; limit_price: number; created_at: string; market_data_source?: string | null; fallback_mode?: boolean | null; fills: Array<{ fill_price: number; filled_shares: number; timestamp: string }> };

export default function Page() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("workflow pending");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const selected = useMemo(() => orders.find((o) => o.order_id === selectedOrderId) ?? null, [orders, selectedOrderId]);

  async function load() {
    if (!isLoaded || !isSignedIn) {
      setFeedback({ state: "loading", message: "Initializing authenticated workflow…" });
      return;
    }
    setBusy(true);
    setError(null);
    setFeedback({ state: "loading", message: "Loading orders…" });
    const result = await fetchWorkflowApi<Order>("/api/user/orders", undefined, { authMode: "token", getToken });
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
    setSelectedOrderId((prev) => prev ?? result.items.find((order) => order.recommendation_id === requestedRecommendation)?.order_id ?? result.items[0]?.order_id ?? null);
    setDataSource((result.items[0]?.fallback_mode ? `fallback (${result.items[0]?.market_data_source ?? "provider"})` : (result.items[0]?.market_data_source ?? "provider")) ?? "workflow pending");
    setBusy(false);
  }

  async function stagePaperOrder() {
    if (!isLoaded || !isSignedIn) {
      setFeedback({ state: "loading", message: "Authentication still initializing." });
      return;
    }
    setStatus("staging paper order...");
    setBusy(true);
    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    const result = await fetchWorkflowApi<{ order_id: string; market_data_source?: string; fallback_mode?: boolean }>(
      "/api/user/orders",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: "AAPL", recommendation_id: requestedRecommendation ?? undefined }) },
      { authMode: "token", getToken },
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
    setStatus("paper order staged");
    setFeedback({ state: "success", message: "Paper order staged." });
    await load();
    setBusy(false);
  }

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    void load();
  }, [searchKey, isLoaded, isSignedIn]);
  useEffect(() => {
    if (feedback.state !== "success") return;
    const timer = window.setTimeout(() => setFeedback({ state: "idle", message: "" }), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback.state, feedback.message]);

  return <section className="op-stack">
    <PageHeader title="Orders blotter" subtitle="Paper/dev execution only. No live trading route is exposed." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <Card title="Blotter mode">
      Generated from recommendation workflow bars sourced from: <strong>{dataSource}</strong>. This is paper-only execution for operator review.
    </Card>
    <Card title="What a good blotter review looks like">
      Confirm the staged order maps to the intended recommendation, source mode, and deterministic sizing before considering live-route promotion.
    </Card>
    {!isLoaded ? <Card title="Auth status">Initializing authenticated session before orders API requests.</Card> : null}
    <Card>
      <div className="op-row">
        <button onClick={() => void stagePaperOrder()} disabled={busy}>{busy ? "Staging..." : "Stage paper order"}</button>
        <button onClick={() => void load()} disabled={busy}>{busy ? "Refreshing..." : "Refresh blotter"}</button>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
    </Card>
    {error ? <ErrorState title="Orders unavailable" hint={error} /> : null}
    {orders.length === 0 && !error ? <EmptyState title="No orders yet" hint="Stage a deterministic paper order to populate the blotter." /> : null}
    <div className="op-grid-2">
      <Card title="Order table">
        <table className="op-table">
          <thead><tr><th>created_at</th><th>symbol</th><th>side</th><th>shares</th><th>limit/fill</th><th>broker status</th><th>fill count</th></tr></thead>
          <tbody>{orders.map((o) => <tr key={o.order_id} onClick={() => setSelectedOrderId(o.order_id)} className={`is-selectable ${selectedOrderId === o.order_id ? "is-active" : ""}`}><td>{o.created_at}</td><td>{o.symbol}</td><td><StatusBadge tone={o.side === "buy" ? "good" : "warn"}>{o.side}</StatusBadge></td><td>{o.shares}</td><td>{o.limit_price} / {o.fills[0]?.fill_price ?? "-"}</td><td><StatusBadge tone={o.status.includes("fill") ? "good" : "warn"}>{o.status}</StatusBadge></td><td>{o.fills.length}</td></tr>)}</tbody>
        </table>
      </Card>
      <Card title="Selected order detail">
        {!selected ? <EmptyState title="Select an order" hint="Click a blotter row to inspect paper-broker fill details." /> : <div style={{ display: "grid", gap: 6 }}>
          <div><strong>Order id:</strong> {selected.order_id}</div>
          <div><strong>Recommendation id:</strong> {selected.recommendation_id || new URLSearchParams(searchKey).get("recommendation") || "pending linkage"}</div>
          <div><strong>Why this paper order exists:</strong> staged from approved recommendation path for operator verification before any live-route discussion.</div>
          <div><strong>Symbol/side:</strong> {selected.symbol} {selected.side}</div>
          <div><strong>Shares:</strong> {selected.shares}</div>
          <div><strong>Limit:</strong> {selected.limit_price}</div>
          <div><strong>Status:</strong> {selected.status}</div>
          <div><strong>Workflow source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)}</div>
          <div><strong>Created at:</strong> {selected.created_at}</div>
          <div><strong>Fills:</strong></div>
          {selected.fills.map((fill, idx) => <div key={idx}>#{idx + 1} {fill.filled_shares} @ {fill.fill_price} ({fill.timestamp})</div>)}
        </div>}
      </Card>
    </div>
  </section>;
}
