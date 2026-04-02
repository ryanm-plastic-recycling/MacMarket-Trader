"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@clerk/nextjs";

import { Card, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalizedAuthed } from "@/lib/api-client";

type Order = { order_id: string; recommendation_id: string; symbol: string; status: string; side: string; shares: number; limit_price: number; created_at: string; market_data_source?: string | null; fallback_mode?: boolean | null; fills: Array<{ fill_price: number; filled_shares: number; timestamp: string }> };

export default function Page() {
  const { getToken } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("workflow unavailable");
  const [busy, setBusy] = useState(false);
  const selected = useMemo(() => orders.find((o) => o.order_id === selectedOrderId) ?? null, [orders, selectedOrderId]);

  async function load() {
    setBusy(true);
    const result = await fetchNormalizedAuthed<Order>("/api/user/orders", undefined, getToken);
    if (!result.ok) {
      setError(result.error);
      setBusy(false);
      return;
    }
    setError(null);
    setOrders(result.items);
    setSelectedOrderId((prev) => prev ?? result.items[0]?.order_id ?? null);
    setDataSource((result.items[0]?.fallback_mode ? `fallback (${result.items[0]?.market_data_source ?? "provider"})` : (result.items[0]?.market_data_source ?? "provider")) ?? "workflow unavailable");
    setBusy(false);
  }

  async function stagePaperOrder() {
    setStatus("staging paper order...");
    setBusy(true);
    const result = await fetchNormalizedAuthed<{ order_id: string; market_data_source?: string; fallback_mode?: boolean }>("/api/user/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: "AAPL" }) }, getToken);
    if (!result.ok) {
      setError(result.error ?? "Unable to stage order.");
      setStatus("failed");
      setBusy(false);
      return;
    }
    setError(null);
    const fallbackMode = result.data?.fallback_mode ?? false;
    const sourceName = result.data?.market_data_source ?? "provider";
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    setStatus("paper order staged");
    await load();
    setBusy(false);
  }

  useEffect(() => { void load(); }, []);

  return <section className="op-stack">
    <PageHeader title="Orders blotter" subtitle="Paper/dev execution only. No live trading route is exposed." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <Card title="Blotter mode">
      Generated from recommendation workflow bars sourced from: <strong>{dataSource}</strong>. This is paper-only execution for operator review.
    </Card>
    <Card>
      <div className="op-row">
        <button onClick={() => void stagePaperOrder()} disabled={busy}>{busy ? "Staging..." : "Stage paper order"}</button>
        <button onClick={() => void load()} disabled={busy}>{busy ? "Refreshing..." : "Refresh blotter"}</button>
      </div>
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
          <div><strong>Recommendation id:</strong> {selected.recommendation_id}</div>
          <div><strong>Symbol/side:</strong> {selected.symbol} {selected.side}</div>
          <div><strong>Shares:</strong> {selected.shares}</div>
          <div><strong>Limit:</strong> {selected.limit_price}</div>
          <div><strong>Status:</strong> {selected.status}</div>
          <div><strong>Workflow source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "unknown"})` : (selected.market_data_source ?? dataSource)}</div>
          <div><strong>Created at:</strong> {selected.created_at}</div>
          <div><strong>Fills:</strong></div>
          {selected.fills.map((fill, idx) => <div key={idx}>#{idx + 1} {fill.filled_shares} @ {fill.fill_price} ({fill.timestamp})</div>)}
        </div>}
      </Card>
    </div>
  </section>;
}
