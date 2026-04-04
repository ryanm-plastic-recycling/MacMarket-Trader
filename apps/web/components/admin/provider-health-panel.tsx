"use client";

import { useEffect, useState } from "react";

import { Card, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type ProviderHealth = {
  providers: Array<{ provider: string; mode: string; status: string; details: string; operational_impact?: string; configured_provider?: string; effective_read_mode?: string; workflow_execution_mode?: string; failure_reason?: string | null; configured?: boolean; feed?: string; sample_symbol?: string; latency_ms?: number | null; last_success_at?: string | null }>;
  checked_at: string;
};

export function ProviderHealthPanel() {
  const [data, setData] = useState<ProviderHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const response = await fetchWorkflowApi<ProviderHealth>("/api/admin/provider-health");
      if (!response.ok) {
        setError(response.error ?? "Failed to load provider health.");
      } else {
        setData(response.data);
      }
      setLoading(false);
    }
    void load();
  }, []);

  if (loading) return <p>Loading provider health…</p>;
  if (error) return <ErrorState title="Provider health unavailable" hint={error} />;

  const market = data?.providers.find((p) => p.provider === "market_data");
  const workflowBlocked = market?.workflow_execution_mode === "blocked";
  const workflowDemoFallback = market?.workflow_execution_mode === "demo_fallback";
  const healthyProvider = market?.workflow_execution_mode === "provider";

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader title="Provider health" subtitle={`Checked at ${data?.checked_at ?? "unknown"}.`} />
      <Card title="Operator summary">
        <div className="op-row">
          <StatusBadge tone={healthyProvider ? "good" : "warn"}>workflow mode: {market?.workflow_execution_mode ?? "-"}</StatusBadge>
          <span>configured provider: {market?.configured_provider ?? "-"}</span>
          <span>effective read mode: {market?.effective_read_mode ?? "-"}</span>
          <span>sample symbol: {market?.sample_symbol ?? "AAPL"}</span>
          <span>latency: {market?.latency_ms ?? "-"} ms</span>
          <span>last success: {market?.last_success_at ?? "-"}</span>
        </div>
        {healthyProvider ? <p style={{ color: "#7ee787" }}>Live provider mode is active and healthy.</p> : null}
        {workflowBlocked ? <p style={{ color: "#f7b267" }}>Configured provider probe failed and workflow demo fallback is disabled. Workflow execution is blocked until provider health recovers.</p> : null}
        {workflowDemoFallback ? <p style={{ color: "#f7b267" }}>Configured provider probe failed or provider mode is disabled; workflows are running on explicit deterministic demo fallback bars.</p> : null}
        {market?.failure_reason ? <p style={{ color: "#9fb0c3" }}>Failure reason: {market.failure_reason}</p> : null}
        <p style={{ color: "#9fb0c3" }}>{market?.operational_impact ?? "Market-data mode determines whether recommendations, replay, and orders run on provider-backed bars or explicit fallback bars."}</p>
      </Card>
      <div className="op-grid-3">
        {data?.providers.map((p) => (
          <Card key={p.provider} title={p.provider}>
            <div><StatusBadge tone={p.status === "ok" ? "good" : "warn"}>{p.status}</StatusBadge> · {p.mode}</div>
            <div style={{ color: "#9fb0c3", marginTop: 6 }}>{p.details}</div>
          </Card>
        ))}
      </div>
    </section>
  );
}
