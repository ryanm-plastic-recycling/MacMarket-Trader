"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { HacoWorkspace } from "@/components/charts/haco-workspace";
import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { GUIDED_ENTRY_PATH, GUIDED_FLOW_LABEL } from "@/lib/guided-workflow";
import { fetchWorkflowApi } from "@/lib/api-client";
import { WorkflowBanner } from "@/components/workflow-banner";

type Recommendation = { id: number; symbol: string; created_at: string; payload: any };
type AuditEvent = { event_type: string; timestamp: string | null; detail: string; status: string };
type DashboardPayload = {
  market_regime: string;
  last_refresh: string;
  account: { app_role: string; approval_status: string };
  provider_health: { summary: string; auth: string; email: string; market_data: string; configured_provider: string; effective_read_mode: string; workflow_execution_mode: string; failure_reason?: string };
  latest_market_snapshot?: { symbol: string; as_of: string; close: number; source: string; fallback_mode: boolean };
  active_recommendations: Recommendation[];
  recent_replay_runs: Array<{ id: number; symbol: string; recommendation_count: number; approved_count: number; created_at: string }>;
  recent_orders: Array<{ order_id: string; symbol: string; status: string; side: string; created_at: string }>;
  pending_admin_actions: Array<{ id: number; email: string; display_name: string }>;
  alerts: Array<{ kind: string; level: string; message: string }>;
  workflow_guide?: string[];
  recent_audit_events?: AuditEvent[];
};
type OnboardingStatus = { has_schedule: boolean; has_replay: boolean; has_order: boolean; has_viewed_haco: boolean | null; completed: number; total: number };

export default function Page() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "loading", message: "Loading operator dashboard…" });
  const [error, setError] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  // True while the first data fetch is in flight — shows "Loading..." instead of "-"
  const loading = !data && feedback.state === "loading";

  useEffect(() => {
    fetchWorkflowApi<DashboardPayload>("/api/user/dashboard").then((result) => {
      if (result.ok) {
        setData(result.data);
        setError(null);
        setFeedback({ state: "success", message: "Dashboard updated." });
        return;
      }
      setError(result.error ?? "Unable to load dashboard.");
      setFeedback({ state: "error", message: result.error ?? "Unable to load dashboard." });
    });
    fetchWorkflowApi<OnboardingStatus>("/api/user/onboarding-status").then((r) => {
      if (r.ok && r.data) {
        const hacoViewed = typeof window !== "undefined" && window.localStorage.getItem("macmarket-haco-visited") === "true";
        setOnboarding({ ...r.data, has_viewed_haco: hacoViewed });
      }
    });
  }, []);

  const latest = useMemo(() => data?.active_recommendations[0] ?? null, [data]);

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader
        title="Operator dashboard"
        subtitle="Canonical private-alpha path: Analyze → Recommendation → Replay → Paper Order."
        actions={<>
          <StatusBadge tone="neutral">{data?.market_regime ?? (loading ? "Loading..." : "-")}</StatusBadge>
          <Link href={GUIDED_ENTRY_PATH}><button>{GUIDED_FLOW_LABEL}</button></Link>
        </>}
      />
      <WorkflowBanner current="Analyze" state={{ guided: false }} nextHref="/analysis" nextLabel="Start from Analyze" compact />
      <InlineFeedback state={feedback.state} message={feedback.message} />
      {error ? <ErrorState title="Dashboard unavailable" hint={error} /> : null}
      {!error && !data ? <EmptyState title="Waiting for dashboard data" hint="Refresh after your auth session initializes." /> : null}
      {onboarding ? (
        <Card title={`Onboarding checklist — ${onboarding.completed + (onboarding.has_viewed_haco ? 1 : 0)}/${onboarding.total}`}>
          <div className="op-grid-2">
            <div>{onboarding.has_replay ? "✅" : "◻"} Run a replay</div>
            <div>{onboarding.has_order ? "✅" : "◻"} Stage a paper order</div>
            <div>{onboarding.has_schedule ? "✅" : "◻"} Create a strategy schedule</div>
            <div>{onboarding.has_viewed_haco ? "✅" : "◻"} Review HACO context</div>
          </div>
        </Card>
      ) : null}

      <div className="op-grid-4">
        <Card title="Account role"><StatusBadge tone="neutral">{data?.account.app_role ?? (loading ? "Loading..." : "-")}</StatusBadge></Card>
        <Card title="Approval"><StatusBadge tone={data?.account.approval_status === "approved" ? "good" : "warn"}>{data?.account.approval_status ?? (loading ? "Loading..." : "-")}</StatusBadge></Card>
        <Card title="Provider summary">
          <StatusBadge tone={data?.provider_health.workflow_execution_mode === "provider" ? "good" : "warn"}>{data?.provider_health.workflow_execution_mode ?? (loading ? "Loading..." : "-")}</StatusBadge>
          <div style={{ marginTop: 8, color: "#9fb0c3" }}>
            configured: {data?.provider_health.configured_provider ?? (loading ? "Loading..." : "-")} · reads: {data?.provider_health.effective_read_mode ?? (loading ? "Loading..." : "-")}
          </div>
        </Card>
        <Card title="Last refresh">{data?.last_refresh ?? (loading ? "Loading..." : "-")}</Card>
      </div>

      <div className="op-grid-2">
        <Card title="Actionable recommendations">
          <div style={{ marginBottom: 8, color: "#9fb0c3" }}>
            Market snapshot source: {data?.latest_market_snapshot?.source ?? "-"}{data?.latest_market_snapshot?.fallback_mode ? " (fallback mode)" : ""}
          </div>
          <table className="op-table"><thead><tr><th>symbol</th><th>thesis</th><th>R/R</th><th>confidence</th></tr></thead>
            <tbody>{data?.active_recommendations.map((r) => <tr key={r.id}><td>{r.symbol}</td><td>{r.payload?.thesis}</td><td>{r.payload?.quality?.expected_rr}</td><td>{r.payload?.quality?.confidence}</td></tr>)}</tbody></table>
          {latest ? <div style={{ marginTop: 10 }}><strong>Selected callout:</strong> {latest.payload?.thesis}</div> : null}
        </Card>
        <Card title="HACO supporting context">
          <HacoWorkspace embedded />
        </Card>
      </div>
      <Card title="Next actions">
        {(data?.workflow_guide ?? []).map((item, idx) => <div key={idx}>{idx + 1}. {item}</div>)}
        {data?.provider_health.failure_reason ? (
          <div style={{ marginTop: 8, color: "#f7b267" }}>
            Provider probe detail: {data.provider_health.failure_reason}
          </div>
        ) : null}
      </Card>

      <div className="op-grid-4">
        <Card title="Recent replay runs">{data?.recent_replay_runs.map((r) => <div key={r.id}>{r.symbol} • {r.recommendation_count}/{r.approved_count}</div>)}</Card>
        <Card title="Recent orders">{data?.recent_orders.map((o) => <div key={o.order_id}>{o.symbol} • {o.side} • {o.status}</div>)}</Card>
        <Card title="Pending admin actions">{data?.pending_admin_actions.map((u) => <div key={u.id}>{u.display_name} ({u.email})</div>)}</Card>
        <Card title="Alert / event log">{data?.alerts.map((a, idx) => <div key={idx}>[{a.level}] {a.message}</div>)}</Card>
      </div>

      <Card title="Operational audit trail">
        {(!data?.recent_audit_events || data.recent_audit_events.length === 0) ? (
          <div style={{ color: "#9fb0c3" }}>No audit events recorded yet.</div>
        ) : (
          <table className="op-table">
            <thead><tr><th>time</th><th>event</th><th>detail</th><th>status</th></tr></thead>
            <tbody>
              {data.recent_audit_events.map((ev, idx) => (
                <tr key={idx}>
                  <td style={{ whiteSpace: "nowrap", color: "#9fb0c3" }}>{ev.timestamp ? new Date(ev.timestamp).toLocaleString() : "—"}</td>
                  <td><StatusBadge tone="neutral">{ev.event_type.replace("_", " ")}</StatusBadge></td>
                  <td>{ev.detail}</td>
                  <td><StatusBadge tone={ev.status === "sent" || ev.status === "ok" ? "good" : ev.status === "pending" ? "warn" : "neutral"}>{ev.status}</StatusBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </section>
  );
}
