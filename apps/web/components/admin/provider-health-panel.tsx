"use client";

import { useEffect, useState } from "react";

type ProviderHealth = {
  providers: Array<{ provider: string; mode: string; status: string; details: string; configured?: boolean; feed?: string; sample_symbol?: string; latency_ms?: number | null; last_success_at?: string | null }>;
  checked_at: string;
};

export function ProviderHealthPanel() {
  const [data, setData] = useState<ProviderHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/admin/provider-health", { cache: "no-store" });
        if (!response.ok) throw new Error(`Failed to load provider health (${response.status})`);
        setData((await response.json()) as ProviderHealth);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load provider health.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  if (loading) return <p>Loading provider health…</p>;
  if (error) return <p style={{ color: "#ff8b8b" }}>{error}</p>;

  return (
    <section>
      <h1>Provider health</h1>
      <p style={{ color: "#9fb0c3" }}>Provider status snapshot checked at {data?.checked_at ?? "unknown"}. Modes and statuses are sourced from backend provider configuration, not placeholders.</p>
      <div style={{ display: "grid", gap: 8 }}>
        {data?.providers.map((p) => (
          <div key={p.provider} style={{ border: "1px solid #2b3642", background: "#111922", padding: 12 }}>
            <strong>{p.provider}</strong> — {p.status} ({p.mode})
            <div style={{ color: "#9fb0c3" }}>{p.details}</div>
            {p.provider === "market_data" ? <div style={{ color: "#9fb0c3", marginTop: 4 }}>feed={p.feed ?? "-"}, configured={String(p.configured ?? false)}, sample={p.sample_symbol ?? "-"}, latency_ms={p.latency_ms ?? "-"}, last_success={p.last_success_at ?? "-"}</div> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
