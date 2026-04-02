"use client";

import { useEffect, useState } from "react";

import { Card, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalized } from "@/lib/api-client";

type ProviderHealth = {
  providers: Array<{ provider: string; mode: string; status: string; details: string; operational_impact?: string; configured?: boolean; feed?: string; sample_symbol?: string; latency_ms?: number | null; last_success_at?: string | null }>;
  checked_at: string;
};

export function ProviderHealthPanel() {
  const [data, setData] = useState<ProviderHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const response = await fetchNormalized<ProviderHealth>("/api/admin/provider-health");
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
  const providerRejected = market?.status !== "ok";

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader title="Provider health" subtitle={`Checked at ${data?.checked_at ?? "unknown"}.`} />
      <Card title="Operator summary">
        <div className="op-row">
          <StatusBadge tone={providerRejected ? "warn" : "good"}>mode: {market?.mode ?? "-"}</StatusBadge>
          <span>sample symbol: {market?.sample_symbol ?? "AAPL"}</span>
          <span>latency: {market?.latency_ms ?? "-"} ms</span>
          <span>last success: {market?.last_success_at ?? "-"}</span>
        </div>
        {providerRejected ? <p style={{ color: "#f7b267" }}>Configured provider rejected current request; workflows are running on fallback bars. Check key, plan/entitlements, and symbol permissions.</p> : <p style={{ color: "#7ee787" }}>Live provider mode is active and healthy.</p>}
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
