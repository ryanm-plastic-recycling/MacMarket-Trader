"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { HacoWorkspace } from "@/components/charts/haco-workspace";

type Recommendation = { id: number; symbol: string; created_at: string; payload: any };
type DashboardPayload = {
  market_regime: string;
  last_refresh: string;
  account: { app_role: string; approval_status: string };
  provider_health: { summary: string; auth: string; email: string; market_data: string };
  latest_market_snapshot?: { symbol: string; as_of: string; close: number; source: string; fallback_mode: boolean };
  active_recommendations: Recommendation[];
  recent_replay_runs: Array<{ id: number; symbol: string; recommendation_count: number; approved_count: number; created_at: string }>;
  recent_orders: Array<{ order_id: string; symbol: string; status: string; side: string; created_at: string }>;
  pending_admin_actions: Array<{ id: number; email: string; display_name: string }>;
  alerts: Array<{ kind: string; level: string; message: string }>;
};

export default function Page() {
  const [data, setData] = useState<DashboardPayload | null>(null);

  useEffect(() => {
    fetch("/api/user/dashboard", { cache: "no-store" }).then((r) => r.json()).then(setData);
  }, []);

  const latest = useMemo(() => data?.active_recommendations[0] ?? null, [data]);

  return (
    <section style={{ display: "grid", gap: 14 }}>
      <div style={{ border: "1px solid #2a3440", background: "#0f1722", padding: 14 }}>
        <h1 style={{ margin: 0 }}>Operator dashboard</h1>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginTop: 8, color: "#9fb0c3" }}>
          <span>Market regime: <strong style={{ color: "#d8e1ef" }}>{data?.market_regime ?? "loading"}</strong></span>
          <span>Role: <strong style={{ color: "#d8e1ef" }}>{data?.account.app_role ?? "-"}</strong></span>
          <span>Approval: <strong style={{ color: "#d8e1ef" }}>{data?.account.approval_status ?? "-"}</strong></span>
          <span>Provider summary: <strong style={{ color: data?.provider_health.summary === "degraded" ? "#f7b267" : "#7ee787" }}>{data?.provider_health.summary ?? "-"}</strong></span>
          <span>Last refresh: {data?.last_refresh ?? "-"}</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1fr", gap: 14 }}>
        <div style={{ border: "1px solid #2a3440", background: "#0f1722", padding: 14 }}>
          <h2 style={{ marginTop: 0 }}>Active recommendations</h2>
          {(data?.active_recommendations.length ?? 0) === 0 ? (
            <div style={{ color: "#9fb0c3" }}>
              No active recommendations yet. Review recent replay, order, and admin queues below while the setup engine compiles new candidates.
            </div>
          ) : (
            <table style={{ width: "100%", fontSize: 13 }}>
              <thead><tr><th align="left">Symbol</th><th align="left">Thesis</th><th>Catalyst</th><th>Entry</th><th>Invalidation</th><th>Target</th><th>R/R</th><th>Conf/Evidence</th></tr></thead>
              <tbody>
                {data?.active_recommendations.map((r) => <tr key={r.id} style={{ borderTop: "1px solid #25303b" }}>
                  <td>{r.symbol}</td><td>{r.payload?.thesis ?? "-"}</td><td>{r.payload?.catalyst?.type ?? "-"}</td><td>{r.payload?.entry?.zone_low ?? "-"} / {r.payload?.entry?.zone_high ?? "-"}</td><td>{r.payload?.invalidation?.price ?? "-"}</td><td>{r.payload?.targets?.target_1 ?? "-"}</td><td>{r.payload?.quality?.expected_rr ?? "-"}</td><td>{r.payload?.quality?.confidence ?? "-"}/{(r.payload?.evidence?.explanatory_notes ?? []).length}</td>
                </tr>)}
              </tbody>
            </table>
          )}
          {latest ? <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #25303b" }}>
            <strong>Selected thesis:</strong> {latest.payload?.thesis}
          </div> : null}
        </div>

        <div style={{ border: "1px solid #2a3440", background: "#0f1722", padding: 14 }}>
          <HacoWorkspace embedded />
          <div style={{ marginTop: 10 }}><Link href="/charts/haco">Open dedicated HACO workspace →</Link></div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: 10 }}>
        <Panel title="Recent replay runs">{data?.recent_replay_runs.map((r) => <div key={r.id}>{r.symbol} • {r.recommendation_count}/{r.approved_count}</div>)}</Panel>
        <Panel title="Recent orders">{data?.recent_orders.map((o) => <div key={o.order_id}>{o.symbol} • {o.side} • {o.status}</div>)}</Panel>
        <Panel title="Pending admin actions">{data?.pending_admin_actions.map((u) => <div key={u.id}>{u.display_name || "Unknown"} ({u.email || "missing email"})</div>)}</Panel>
        <Panel title="Provider health details">
          <div>Auth: {data?.provider_health.auth}</div><div>Email: {data?.provider_health.email}</div><div>Market data: {data?.provider_health.market_data}</div><div>Snapshot: {data?.latest_market_snapshot?.symbol ?? "-"} @ {data?.latest_market_snapshot?.close ?? "-"}</div><div>Source: {data?.latest_market_snapshot?.source ?? "-"}{data?.latest_market_snapshot?.fallback_mode ? " (fallback)" : ""}</div>
        </Panel>
        <Panel title="Alert / event log">{data?.alerts.map((a, idx) => <div key={idx}>[{a.level}] {a.message}</div>)}</Panel>
      </div>
    </section>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={{ border: "1px solid #2a3440", background: "#0f1722", padding: 10 }}><h3 style={{ marginTop: 0, fontSize: 14 }}>{title}</h3><div style={{ color: "#c4d0df", fontSize: 13, display: "grid", gap: 6 }}>{children || <span style={{ color: "#8396ab" }}>No recent data.</span>}</div></div>;
}
