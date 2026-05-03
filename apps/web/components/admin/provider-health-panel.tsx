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
    config_state?: "configured" | "missing_config" | "disabled" | string;
    probe_state?: "ok" | "failed" | "skipped" | "unavailable" | string;
    configured?: boolean;
    credentials_present?: boolean;
    paper_routing_enabled?: boolean;
    account_probe_endpoint?: string | null;
    account_status?: string | null;
    order_route_probe?: string | null;
    feed?: string;
    sample_symbol?: string;
    sample_series?: string | null;
    sample_underlying?: string | null;
    sample_option_symbol?: string | null;
    sample_selection_method?: string | null;
    sample_mark_method?: string | null;
    latency_ms?: number | null;
    last_success_at?: string | null;
    selected_provider?: string;
    probe_status?: string;
    readiness_scope?: string;
    entitlement_state?: string | null;
    llm_enabled?: boolean;
    model?: string | null;
    key_present?: boolean;
    fallback_active?: boolean;
    fallback_reason?: string | null;
    last_error?: string | null;
    last_openai_error?: {
      endpoint?: string | null;
      model?: string | null;
      status_code?: number | null;
      error_type?: string | null;
      error_code?: string | null;
      message?: string | null;
      request_id?: string | null;
    } | null;
  }>;
  checked_at: string;
};

export const OPTIONS_PROVIDER_READINESS_NOTE =
  "Options/index data note: SPX/NDX may require index data access; SPY/QQQ can be practical ETF substitutes. Options chain, IV, Greeks, open interest, and option snapshot marks depend on provider coverage. If the plan is not entitled, Options Position Review shows mark_unavailable rather than fake P&L. This readiness view does not enable execution.";

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
  const optionsData = data?.providers.find((p) => p.provider === "options_data");
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
      case "disabled":
        return "Disabled";
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
      case "disabled":
        return "neutral";
      case "unconfigured":
        return "warn";
      default:
        return "warn";
    }
  }

  function formatConfigLabel(configState: string | undefined): string {
    switch ((configState ?? "").toLowerCase()) {
      case "configured":
        return "Configured";
      case "missing_config":
        return "Missing config";
      case "disabled":
        return "Disabled";
      default:
        return "Unknown config";
    }
  }

  function configTone(configState: string | undefined): "good" | "warn" | "neutral" {
    switch ((configState ?? "").toLowerCase()) {
      case "configured":
        return "neutral";
      case "missing_config":
        return "warn";
      default:
        return "neutral";
    }
  }

  function formatProbeLabel(probeState: string | undefined): string | null {
    switch ((probeState ?? "").toLowerCase()) {
      case "unavailable":
        return "Probe unavailable";
      case "ok":
        return "Probe OK";
      case "skipped":
        return "Probe not run";
      case "failed":
        return "Probe failed";
      default:
        return null;
    }
  }

  function probeTone(probeState: string | undefined): "good" | "warn" | "neutral" {
    switch ((probeState ?? "").toLowerCase()) {
      case "ok":
        return "good";
      case "failed":
        return "warn";
      default:
        return "neutral";
    }
  }

  function providerDetailCopy(provider: ProviderHealth["providers"][number]): string {
    if (provider.provider === "options_data" && provider.entitlement_state === "not_entitled") {
      return "Options data is configured, but the provider plan is not entitled to option snapshot marks. Options marks remain unavailable; no fake option P&L is shown.";
    }
    if (provider.config_state === "configured" && provider.probe_state === "unavailable") {
      if (provider.provider === "alpaca_paper") {
        return "Required config appears present. No safe live probe is currently implemented. Paper-provider readiness only. Order routing is not enabled.";
      }
      return "Required config appears present. No safe live probe is currently implemented.";
    }
    if (provider.config_state === "missing_config" || provider.status === "unconfigured") {
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
          {alpacaPaper ? <StatusBadge tone={configTone(alpacaPaper.config_state)}>alpaca paper: {formatConfigLabel(alpacaPaper.config_state)} / {formatProbeLabel(alpacaPaper.probe_state) ?? "Probe unknown"}</StatusBadge> : null}
          {fred ? <StatusBadge tone="neutral">fred: {formatConfigLabel(fred.config_state)} / {formatProbeLabel(fred.probe_state) ?? "Probe unknown"}</StatusBadge> : null}
          {news ? <StatusBadge tone="neutral">news: {formatConfigLabel(news.config_state)} / {formatProbeLabel(news.probe_state) ?? "Probe unknown"}</StatusBadge> : null}
          {optionsData ? <StatusBadge tone={probeTone(optionsData.probe_state)}>options data: {formatConfigLabel(optionsData.config_state)} / {formatProbeLabel(optionsData.probe_state) ?? "Probe unknown"}</StatusBadge> : null}
          {llm ? <StatusBadge tone={statusTone(llm.status)}>LLM provider: {llm.mode} / {formatStatusLabel(llm.status)} / {formatProbeLabel(llm.probe_state) ?? "Probe unknown"}</StatusBadge> : null}
        </div>
        {healthyProvider ? <p style={{ color: "#7ee787", margin: "8px 0 0" }}>Provider-backed market-data mode is active and healthy.</p> : null}
        {workflowBlocked ? <p style={{ color: "#f7b267", margin: "8px 0 0" }}>Configured provider probe failed and workflow demo fallback is disabled. Workflow execution is blocked until provider health recovers.</p> : null}
        {workflowDemoFallback ? <p style={{ color: "#f7b267", margin: "8px 0 0" }}>Configured provider probe failed or provider mode is disabled; workflows are running on explicit deterministic demo fallback bars.</p> : null}
        {market?.failure_reason ? <p style={{ ...muted, margin: "6px 0 0" }}>Failure reason: {market.failure_reason}</p> : null}
        <p style={{ ...muted, margin: "6px 0 0" }}>{market?.operational_impact ?? "Market-data mode determines whether recommendations, replay, and orders run on provider-backed bars or explicit fallback bars."}</p>
        <p style={{ ...muted, margin: "6px 0 0" }}>
          Market data is healthy only when the Polygon probe succeeds. Optional providers can be configured while their probe is unavailable; that is readiness context, not health.
          {llm?.fallback_active ? " LLM fallback is currently active or degraded; deterministic recommendations still run." : ""}
        </p>
        <p style={{ ...muted, margin: "6px 0 0" }}>
          Alpaca readiness on this page is paper-provider readiness only. No live brokerage execution or credential entry is enabled here.
        </p>
        <p style={{ ...muted, margin: "6px 0 0" }}>
          {OPTIONS_PROVIDER_READINESS_NOTE}
        </p>
        {optionsData?.entitlement_state === "not_entitled" ? (
          <p style={{ color: "#f7b267", margin: "6px 0 0" }}>
            Options marks unavailable: provider plan is not entitled to option snapshot data. Options Position Review remains honest and will show mark_unavailable.
          </p>
        ) : null}
      </Card>

      <div className="op-grid-3">
        {data?.providers.map((p) => {
          const probeLabel = formatProbeLabel(p.probe_state ?? p.probe_status);
          return (
            <Card key={p.provider} title={p.provider}>
              <div style={{ display: "grid", gap: 4 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <StatusBadge tone={statusTone(p.status)}>{formatStatusLabel(p.status)}</StatusBadge>
                  {p.config_state ? <StatusBadge tone={configTone(p.config_state)}>{formatConfigLabel(p.config_state)}</StatusBadge> : null}
                  {probeLabel ? <StatusBadge tone={probeTone(p.probe_state ?? p.probe_status)}>{probeLabel}</StatusBadge> : null}
                  <span style={{ fontSize: "0.82rem" }}>{p.mode}</span>
                </div>
                {p.configured !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>configured: </span>{p.configured ? "yes" : "no"}
                  </div>
                ) : null}
                {p.credentials_present !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>credentials present: </span>{p.credentials_present ? "yes" : "no"}
                  </div>
                ) : null}
                {p.paper_routing_enabled !== undefined ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>paper routing enabled: </span>{p.paper_routing_enabled ? "yes" : "no"}
                  </div>
                ) : null}
                {p.account_status ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>paper account status: </span>{p.account_status}</div> : null}
                {p.account_probe_endpoint ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>account probe: </span>{p.account_probe_endpoint}</div> : null}
                {p.order_route_probe ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>order route probe: </span>{p.order_route_probe}</div> : null}
                {p.selected_provider ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>selected mode: </span>{p.selected_provider}
                  </div>
                ) : null}
                {p.probe_status ? (
                  <div style={{ fontSize: "0.8rem" }}>
                    <span style={muted}>probe state: </span>{probeLabel ?? p.probe_state ?? p.probe_status}
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
                {p.sample_symbol ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>sample symbol: </span>{p.sample_symbol}</div> : null}
                {p.sample_series ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>sample series: </span>{p.sample_series}</div> : null}
                {p.sample_underlying ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>sample underlying: </span>{p.sample_underlying}</div> : null}
                {p.sample_option_symbol ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>sample option: </span>{p.sample_option_symbol}</div> : null}
                {p.sample_selection_method ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>sample method: </span>{p.sample_selection_method}</div> : null}
                {p.sample_mark_method ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>mark method: </span>{p.sample_mark_method}</div> : null}
                {p.latency_ms != null ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>latency: </span>{p.latency_ms} ms</div> : null}
                {p.last_success_at ? <div style={{ fontSize: "0.8rem" }}><span style={muted}>last success: </span>{p.last_success_at}</div> : null}
                {p.failure_reason ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>failure: {p.failure_reason}</div> : null}
                {p.fallback_reason ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>fallback: {p.fallback_reason}</div> : null}
                {p.last_error ? <div style={{ fontSize: "0.8rem", color: "#f7b267" }}>last error: {p.last_error}</div> : null}
                {p.last_openai_error ? (
                  <div style={{ fontSize: "0.8rem", color: "#f7b267", display: "grid", gap: 2 }}>
                    <div>OpenAI status: {p.last_openai_error.status_code ?? "-"}</div>
                    <div>OpenAI error: {p.last_openai_error.error_type ?? "-"} / {p.last_openai_error.error_code ?? "-"}</div>
                    <div>OpenAI request id: {p.last_openai_error.request_id ?? "-"}</div>
                    <div>OpenAI endpoint: {p.last_openai_error.endpoint ?? "-"}</div>
                    <div>OpenAI message: {p.last_openai_error.message ?? "-"}</div>
                  </div>
                ) : null}
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
