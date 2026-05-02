"use client";

import { useEffect, useState } from "react";

import { Card, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { MetricLabel } from "@/components/ui/metric-help";
import { fetchWorkflowApi } from "@/lib/api-client";

type ProviderHealth = {
  providers: Array<{
    provider: string;
    mode: string;
    status: string;
    details: string;
    operational_impact?: string;
    configured_provider?: string;
    effective_read_mode?: string;
    workflow_execution_mode?: string;
    failure_reason?: string | null;
    configured?: boolean;
    feed?: string;
    sample_symbol?: string;
    latency_ms?: number | null;
    last_success_at?: string | null;
    selected_provider?: string;
    probe_status?: string;
    readiness_scope?: string;
    llm_enabled?: boolean;
    model?: string | null;
    key_present?: boolean;
    fallback_reason?: string | null;
    last_error?: string | null;
  }>;
  checked_at: string;
};

export const OPTIONS_PROVIDER_READINESS_NOTE =
  "Options/index data note: SPX/NDX may require index data access; SPY/QQQ can be practical ETF substitutes. Options chain, IV, Greeks, and open interest depend on provider coverage. This readiness view does not enable execution.";

export function ProviderHealthPanel() {
  const [data, setData] = useState<ProviderHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reprobing, setReprobing] = useState(false);

  async function load(options?: { probeLlm?: boolean }) {
    setLoading(true);
    setError(null);
    const path = options?.probeLlm ? "/api/admin/provider-health?probe_llm=true" : "/api/admin/provider-health";
    const response = await fetchWorkflowApi<ProviderHealth>(path);
    if (!response.ok) {
      setError(response.error ?? "Failed to load provider readiness.");
    } else {
      setData(response.data);
    }
    setLoading(false);
  }

  async function reprobe() {
    setReprobing(true);
    await load({ probeLlm: true });
    setReprobing(false);
  }

  useEffect(() => { void load(); }, []);

  if (loading && !data) return <p>Loading provider readiness…</p>;
  if (error && !data) return <ErrorState title="Provider readiness unavailable" hint={error} />;

  const market = data?.providers.find((p) => p.provider === "market_data");
  const alpacaPaper = data?.providers.find((p) => p.provider === "alpaca_paper");
  const fred = data?.providers.find((p) => p.provider === "fred");
  const news = data?.providers.find((p) => p.provider === "news");
  const llm = data?.providers.find((p) => p.provider === "llm");
  const workflowBlocked = market?.workflow_execution_mode === "blocked";
  const workflowDemoFallback = market?.workflow_execution_mode === "demo_fallback";
  const healthyProvider = market?.workflow_execution_mode === "provider";

  const muted = { color: "#9fb0c3" } as const;

  function formatStatusLabel(status: string | undefined): string {
    switch ((status ?? "").toLowerCase()) {
      case "ok":
        return "OK";
      case "configured":
        return "Configured";
      case "unconfigured":
        return "Unconfigured";
      default:
        return "Degraded";
    }
  }

  function statusTone(status: string | undefined): "good" | "warn" | "neutral" {
    switch ((status ?? "").toLowerCase()) {
      case "ok":
        return "good";
      case "configured":
        return "neutral";
      case "unconfigured":
        return "warn";
      default:
        return "warn";
    }
  }

  function formatProbeLabel(probeStatus: string | undefined): string | null {
    switch ((probeStatus ?? "").toLowerCase()) {
      case "unavailable":
        return "Probe unavailable";
      case "ok":
        return "Probe OK";
      case "degraded":
      case "warning":
        return "Probe degraded";
      default:
        return null;
    }
  }

  function providerDetailCopy(provider: ProviderHealth["providers"][number]): string {
    if (provider.status === "configured" && provider.probe_status === "unavailable") {
      if (provider.provider === "alpaca_paper") {
        return "Required config appears present. No safe live probe is currently implemented. Paper-provider readiness only. Order routing is not enabled.";
      }
      return "Required config appears present. No safe live probe is currently implemented.";
    }
    if (provider.status === "unconfigured") {
      return "Required configuration is missing or incomplete.";
    }
    return provider.details;
  }

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader
        title="Provider readiness"
        subtitle={`Checked at ${data?.checked_at ?? "unknown"}. This console is for workflow and provider readiness, not live-trading enablement.`}
        actions={
          <button onClick={() => void reprobe()} disabled={reprobing || loading} style={{ fontSize: "0.82rem" }}>
            {reprobing ? "Re-probing…" : "Re-probe now"}
          </button>
        }
      />

      <Card title="Operator summary">
        <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: 8 }}>
          <MetricLabel label="Provider readiness" term="provider_readiness" />
        </div>
        <div className="op-row" style={{ flexWrap: "wrap" }}>
          <StatusBadge tone={healthyProvider ? "good" : "warn"}>workflow mode: {market?.workflow_execution_mode ?? "-"}</StatusBadge>
          <span>configured: <strong>{market?.configured_provider ?? "-"}</strong></span>
          <span>reads: <strong>{market?.effective_read_mode ?? "-"}</strong></span>
          <span>sample: {market?.sample_symbol ?? "AAPL"}</span>
          {market?.latency_ms != null ? <span>latency: {market.latency_ms} ms</span> : null}
          {market?.last_success_at ? <span style={muted}>last success: {market.last_success_at}</span> : null}
        </div>
        <div className="op-row" style={{ flexWrap: "wrap", marginTop: 8 }}>
          {alpacaPaper ? <StatusBadge tone={statusTone(alpacaPaper.status)}>alpaca paper: {formatStatusLabel(alpacaPaper.status)}</StatusBadge> : null}
          {fred ? <StatusBadge tone={statusTone(fred.status)}>fred: {formatStatusLabel(fred.status)}</StatusBadge> : null}
          {news ? <StatusBadge tone={statusTone(news.status)}>news: {formatStatusLabel(news.status)}</StatusBadge> : null}
          {llm ? <StatusBadge tone={statusTone(llm.status)}>LLM provider: {llm.mode} / {formatStatusLabel(llm.status)}</StatusBadge> : null}
        </div>
        {healthyProvider ? <p style={{ color: "#7ee787", margin: "8px 0 0" }}>Provider-backed market-data mode is active and healthy.</p> : null}
        {workflowBlocked ? <p style={{ color: "#f7b267", margin: "8px 0 0" }}>Configured provider probe failed and workflow demo fallback is disabled. Workflow execution is blocked until provider health recovers.</p> : null}
        {workflowDemoFallback ? <p style={{ color: "#f7b267", margin: "8px 0 0" }}>Configured provider probe failed or provider mode is disabled; workflows are running on explicit deterministic demo fallback bars.</p> : null}
        {market?.failure_reason ? <p style={{ ...muted, margin: "6px 0 0" }}>Failure reason: {market.failure_reason}</p> : null}
        <p style={{ ...muted, margin: "6px 0 0" }}>{market?.operational_impact ?? "Market-data mode determines whether recommendations, replay, and orders run on provider-backed bars or explicit fallback bars."}</p>
        <p style={{ ...muted, margin: "6px 0 0" }}>
          Configured means required config appears present. Probe unavailable means no safe live check is currently implemented.
        </p>
        <p style={{ ...muted, margin: "6px 0 0" }}>
          Alpaca readiness on this page is paper-provider readiness only. No live brokerage execution or credential entry is enabled here.
        </p>
        <p style={{ ...muted, margin: "6px 0 0" }}>
          {OPTIONS_PROVIDER_READINESS_NOTE}
        </p>
      </Card>

      <div className="op-grid-3">
        {data?.providers.map((p) => {
          const probeLabel = formatProbeLabel(p.probe_status);
          return (
            <Card key={p.provider} title={p.provider}>
              <div style={{ display: "grid", gap: 4 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <StatusBadge tone={statusTone(p.status)}>{formatStatusLabel(p.status)}</StatusBadge>
                  {probeLabel ? <StatusBadge tone="neutral">{probeLabel}</StatusBadge> : null}
                  <span style={{ fontSize: "0.82rem" }}>{p.mode}</span>
                </div>
                {p.configured !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>configured: </span>{p.configured ? "yes" : "no"}
                  </div>
                ) : null}
                {p.selected_provider ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>selected mode: </span>{p.selected_provider}
                  </div>
                ) : null}
                {p.probe_status ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>live probe: </span>{probeLabel ?? p.probe_status}
                  </div>
                ) : null}
                {p.llm_enabled !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>LLM enabled: </span>{p.llm_enabled ? "yes" : "no"}
                  </div>
                ) : null}
                {p.model ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>model: </span>{p.model}</div> : null}
                {p.key_present !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>key present: </span>{p.key_present ? "yes" : "no"}
                  </div>
                ) : null}
                {p.readiness_scope ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>scope: </span>{p.readiness_scope}
                  </div>
                ) : null}
                {p.feed ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>feed: </span>{p.feed}</div> : null}
                {p.latency_ms != null ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>latency: </span>{p.latency_ms} ms</div> : null}
                {p.last_success_at ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>last success: </span>{p.last_success_at}</div> : null}
                {p.failure_reason ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>failure: {p.failure_reason}</div> : null}
                {p.fallback_reason ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>fallback: {p.fallback_reason}</div> : null}
                {p.last_error ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>last error: {p.last_error}</div> : null}
                {providerDetailCopy(p) ? <div style={{ ...muted, fontSize: "0.78rem", marginTop: 2 }}>{providerDetailCopy(p)}</div> : null}
                {p.operational_impact ? <div style={{ ...muted, fontSize: "0.78rem" }}>{p.operational_impact}</div> : null}
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
