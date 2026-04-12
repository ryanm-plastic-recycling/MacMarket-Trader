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
  const [reprobing, setReprobing] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    const response = await fetchWorkflowApi<ProviderHealth>("/api/admin/provider-health");
    if (!response.ok) {
      setError(response.error ?? "Failed to load provider health.");
    } else {
      setData(response.data);
    }
    setLoading(false);
  }

  async function reprobe() {
    setReprobing(true);
    await load();
    setReprobing(false);
  }

  useEffect(() => { void load(); }, []);

  if (loading && !data) return <p>Loading provider health…</p>;
  if (error && !data) return <ErrorState title="Provider health unavailable" hint={error} />;

  const market = data?.providers.find((p) => p.provider === "market_data");
  const workflowBlocked = market?.workflow_execution_mode === "blocked";
  const workflowDemoFallback = market?.workflow_execution_mode === "demo_fallback";
  const healthyProvider = market?.workflow_execution_mode === "provider";

  const muted = { color: "#9fb0c3" } as const;

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader
        title="Provider health"
        subtitle={`Checked at ${data?.checked_at ?? "unknown"}.`}
        actions={
          <button onClick={() => void reprobe()} disabled={reprobing || loading} style={{ fontSize: "0.82rem" }}>
            {reprobing ? "Re-probing…" : "Re-probe now"}
          </button>
        }
      />

      <Card title="Operator summary">
        <div className="op-row" style={{ flexWrap: "wrap" }}>
          <StatusBadge tone={healthyProvider ? "good" : "warn"}>workflow mode: {market?.workflow_execution_mode ?? "-"}</StatusBadge>
          <span>configured: <strong>{market?.configured_provider ?? "-"}</strong></span>
          <span>reads: <strong>{market?.effective_read_mode ?? "-"}</strong></span>
          <span>sample: {market?.sample_symbol ?? "AAPL"}</span>
          {market?.latency_ms != null ? <span>latency: {market.latency_ms} ms</span> : null}
          {market?.last_success_at ? <span style={muted}>last success: {market.last_success_at}</span> : null}
        </div>
        {healthyProvider ? <p style={{ color: "#7ee787", margin: "8px 0 0" }}>Live provider mode is active and healthy.</p> : null}
        {workflowBlocked ? <p style={{ color: "#f7b267", margin: "8px 0 0" }}>Configured provider probe failed and workflow demo fallback is disabled. Workflow execution is blocked until provider health recovers.</p> : null}
        {workflowDemoFallback ? <p style={{ color: "#f7b267", margin: "8px 0 0" }}>Configured provider probe failed or provider mode is disabled; workflows are running on explicit deterministic demo fallback bars.</p> : null}
        {market?.failure_reason ? <p style={{ ...muted, margin: "6px 0 0" }}>Failure reason: {market.failure_reason}</p> : null}
        <p style={{ ...muted, margin: "6px 0 0" }}>{market?.operational_impact ?? "Market-data mode determines whether recommendations, replay, and orders run on provider-backed bars or explicit fallback bars."}</p>
      </Card>

      <div className="op-grid-3">
        {data?.providers.map((p) => {
          const isOk = p.status === "ok";
          return (
            <Card key={p.provider} title={p.provider}>
              <div style={{ display: "grid", gap: 4 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <StatusBadge tone={isOk ? "good" : "warn"}>{p.status}</StatusBadge>
                  <span style={{ fontSize: "0.82rem" }}>{p.mode}</span>
                </div>
                {p.configured !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>configured: </span>{p.configured ? "yes" : "no"}
                  </div>
                ) : null}
                {p.feed ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>feed: </span>{p.feed}</div> : null}
                {p.latency_ms != null ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>latency: </span>{p.latency_ms} ms</div> : null}
                {p.last_success_at ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>last success: </span>{p.last_success_at}</div> : null}
                {p.failure_reason ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>failure: {p.failure_reason}</div> : null}
                {p.details ? <div style={{ ...muted, fontSize: "0.78rem", marginTop: 2 }}>{p.details}</div> : null}
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
