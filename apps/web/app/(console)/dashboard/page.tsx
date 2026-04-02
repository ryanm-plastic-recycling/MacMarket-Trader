"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { HacoWorkspace } from "@/components/charts/haco-workspace";
import { Card, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalized } from "@/lib/api-client";

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
    fetchNormalized<DashboardPayload>("/api/user/dashboard").then((result) => {
      if (result.ok) setData(result.data);
    });
  }, []);

  const latest = useMemo(() => data?.active_recommendations[0] ?? null, [data]);

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader
        title="Operator dashboard"
        subtitle="Decision hub for recommendations, replay, paper orders, and admin queue."
        actions={<>
          <StatusBadge tone="neutral">{data?.market_regime ?? "loading"}</StatusBadge>
          <Link href="/recommendations"><button>Open recommendations</button></Link>
          <Link href="/replay-runs"><button>Run replay</button></Link>
        </>}
      />

      <div className="op-grid-4">
        <Card title="Account role"><StatusBadge tone="neutral">{data?.account.app_role ?? "-"}</StatusBadge></Card>
        <Card title="Approval"><StatusBadge tone={data?.account.approval_status === "approved" ? "good" : "warn"}>{data?.account.approval_status ?? "-"}</StatusBadge></Card>
        <Card title="Provider summary"><StatusBadge tone={data?.provider_health.summary === "ok" ? "good" : "warn"}>{data?.provider_health.market_data ?? "-"}</StatusBadge></Card>
        <Card title="Last refresh">{data?.last_refresh ?? "-"}</Card>
      </div>

      <div className="op-grid-2">
        <Card title="Actionable recommendations">
          <table className="op-table"><thead><tr><th>symbol</th><th>thesis</th><th>R/R</th><th>confidence</th></tr></thead>
            <tbody>{data?.active_recommendations.map((r) => <tr key={r.id}><td>{r.symbol}</td><td>{r.payload?.thesis}</td><td>{r.payload?.quality?.expected_rr}</td><td>{r.payload?.quality?.confidence}</td></tr>)}</tbody></table>
          {latest ? <div style={{ marginTop: 10 }}><strong>Selected callout:</strong> {latest.payload?.thesis}</div> : null}
        </Card>
        <Card title="HACO supporting context">
          <HacoWorkspace embedded />
        </Card>
      </div>

      <div className="op-grid-4">
        <Card title="Recent replay runs">{data?.recent_replay_runs.map((r) => <div key={r.id}>{r.symbol} • {r.recommendation_count}/{r.approved_count}</div>)}</Card>
        <Card title="Recent orders">{data?.recent_orders.map((o) => <div key={o.order_id}>{o.symbol} • {o.side} • {o.status}</div>)}</Card>
        <Card title="Pending admin actions">{data?.pending_admin_actions.map((u) => <div key={u.id}>{u.display_name} ({u.email})</div>)}</Card>
        <Card title="Alert / event log">{data?.alerts.map((a, idx) => <div key={idx}>[{a.level}] {a.message}</div>)}</Card>
      </div>
    </section>
  );
}
