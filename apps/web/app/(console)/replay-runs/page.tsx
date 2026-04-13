"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, parseGuidedFlowState } from "@/lib/guided-workflow";

type Run = { id: number; symbol: string; created_at: string; recommendation_count: number; approved_count: number; fill_count: number; ending_heat: number; ending_open_notional: number; market_data_source?: string; fallback_mode?: boolean | null };
type Step = { id: number; step_index: number; recommendation_id: string; approved: boolean; pre_step_snapshot: Record<string, unknown>; post_step_snapshot: Record<string, unknown> };

function fmt(v: unknown, digits = 2): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toFixed(digits);
}

function SnapshotRow({ label, pre, post, field, digits = 2 }: { label: string; pre: Record<string, unknown>; post: Record<string, unknown>; field: string; digits?: number }) {
  const preVal = fmt(pre[field], digits);
  const postVal = fmt(post[field], digits);
  const changed = preVal !== postVal;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 1fr", gap: 4, fontSize: "0.82rem", padding: "2px 0" }}>
      <span style={{ color: "var(--op-muted, #7a8999)" }}>{label}</span>
      <span>{preVal}</span>
      <span style={changed ? { color: Number(post[field]) > Number(pre[field]) ? "#4caf50" : "#f44336", fontWeight: 600 } : {}}>{postVal}</span>
    </div>
  );
}

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const guidedState = useMemo(() => parseGuidedFlowState(searchParams), [searchParams]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("workflow pending");
  const [busy, setBusy] = useState(false);
  const [expandedStepId, setExpandedStepId] = useState<number | null>(null);
  const [showOperatorDetail, setShowOperatorDetail] = useState(false);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const selected = useMemo(() => runs.find((r) => r.id === selectedRunId) ?? null, [runs, selectedRunId]);
  const selectedSource = selected ? (selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? "provider")) : dataSource;

  async function loadRuns() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Initializing authenticated workflow…" });
      return;
    }
    setBusy(true);
    setError(null);
    setStepError(null);
    setFeedback({ state: "loading", message: "Loading replay runs…" });
    const result = await fetchWorkflowApi<Run>("/api/user/replay-runs");
    if (!result.ok) {
      if (result.authPending) {
        setError(null);
        setStepError(null);
        setFeedback({ state: "loading", message: "Authentication initializing. Retrying shortly…" });
        setBusy(false);
        return;
      }
      const message = result.status === 503
        ? "Configured provider unavailable. Replay is blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Replay load failed.");
      setError(message);
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }
    setError(null);
    setStepError(null);
    setFeedback({ state: "success", message: "Replay runs updated." });
    setRuns(result.items);
    const requestedSymbol = new URLSearchParams(searchKey).get("symbol");
    const requestedRun = new URLSearchParams(searchKey).get("replay_run");
    setSelectedRunId((prev) => prev
      ?? result.items.find((run) => String(run.id) === requestedRun)?.id
      ?? result.items.find((run) => run.symbol === requestedSymbol)?.id
      ?? result.items[0]?.id
      ?? null);
    setBusy(false);
  }

  async function runReplay() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Authentication still initializing." });
      return;
    }
    setStatus("running replay...");
    setBusy(true);
    const preferredSymbol = new URLSearchParams(searchKey).get("symbol") ?? selected?.symbol ?? "AAPL";
    const run = await fetchWorkflowApi<{ id: number; market_data_source?: string; fallback_mode?: boolean }>(
      "/api/user/replay-runs",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: preferredSymbol }) }
    );
    if (!run.ok) {
      if (run.authPending) {
        setFeedback({ state: "loading", message: "Authentication initializing. Retry in a moment." });
        setBusy(false);
        return;
      }
      const message = run.status === 503
        ? "Configured provider unavailable. Replay is blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (run.error ?? "Replay failed.");
      setError(message);
      setStatus("failed");
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }
    setError(null);
    setStepError(null);
    const fallbackMode = run.data?.fallback_mode ?? false;
    const sourceName = run.data?.market_data_source ?? "provider";
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    setStatus("replay complete");
    setFeedback({ state: "success", message: "Replay run completed." });
    setSelectedRunId(run.data?.id ?? null);
    await loadRuns();
    setBusy(false);
  }

  function openOrdersNextAction() {
    const query = buildGuidedQuery({
      guided: guidedState.guided,
      symbol: selected?.symbol ?? guidedState.symbol,
      strategy: guidedState.strategy,
      recommendationId: guidedState.recommendationId,
      replayRunId: selectedRunId != null ? String(selectedRunId) : guidedState.replayRunId,
    });
    router.push(`/orders?${query}`);
  }

  async function loadSteps(runId: number) {
    if (!authReady) return;
    setSelectedRunId(runId);
    setBusy(true);
    setStepError(null);
    const result = await fetchWorkflowApi<Step>(`/api/user/replay-runs/${runId}/steps`);
    if (!result.ok) {
      if (result.authPending) {
        setStepError(null);
        setFeedback({ state: "loading", message: "Authentication initializing while loading replay steps…" });
        setBusy(false);
        return;
      }
      const message = result.status === 503
        ? "Configured provider unavailable. Replay steps are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Unable to load run steps.");
      setStepError(message);
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }
    setStepError(null);
    setError(null);
    setSteps(result.items);
    setBusy(false);
  }

  useEffect(() => {
    if (!authReady) return;
    void loadRuns();
  }, [searchKey, isLoaded, isSignedIn]);
  useEffect(() => { if (selectedRunId && isLoaded && isSignedIn) void loadSteps(selectedRunId); }, [selectedRunId, isLoaded, isSignedIn]);
  useEffect(() => {
    if (feedback.state !== "success") return;
    const timer = window.setTimeout(() => setFeedback({ state: "idle", message: "" }), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback.state, feedback.message]);

  const approvedCount = steps.filter((s) => s.approved).length;
  const rejectedCount = steps.length - approvedCount;

  const equityPoints = steps.map((s) => Number(s.post_step_snapshot?.equity ?? 0)).filter((v) => v > 0);
  const equitySvg = (() => {
    if (equityPoints.length < 2) return null;
    const W = 280; const H = 52; const pad = 4;
    const minV = Math.min(...equityPoints);
    const maxV = Math.max(...equityPoints);
    const range = maxV - minV || 1;
    const pts = equityPoints.map((v, i) => {
      const x = pad + (i / (equityPoints.length - 1)) * (W - pad * 2);
      const y = H - pad - ((v - minV) / range) * (H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const startColor = equityPoints[equityPoints.length - 1] >= equityPoints[0] ? "#4caf50" : "#f44336";
    return (
      <svg width={W} height={H} style={{ display: "block", margin: "8px 0" }}>
        <polyline points={pts} fill="none" stroke={startColor} strokeWidth="2" strokeLinejoin="round" />
        <text x={pad} y={H - 1} fontSize="9" fill="#9fb0c3">{minV.toFixed(0)}</text>
        <text x={W - pad} y={H - 1} fontSize="9" fill="#9fb0c3" textAnchor="end">{maxV.toFixed(0)}</text>
      </svg>
    );
  })();

  return <section className="op-stack">
    <PageHeader title="Replay workspace" subtitle="Run deterministic replay from recommendation context and inspect step-by-step risk transitions." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    {guidedState.guided ? (
      <Card title="Guided flow progress">
        <GuidedStepRail current="Replay" />
      </Card>
    ) : null}
    {guidedState.guided ? (
      <Card title="Next action">
        <div>After confirming replay path quality, stage a paper order linked to this recommendation lineage.</div>
        <div className="op-row" style={{ marginTop: 8 }}>
          <button onClick={openOrdersNextAction}>Stage paper order</button>
        </div>
      </Card>
    ) : null}
    <Card title="What replay is for">
      Use replay to validate whether a recommendation logic path behaves consistently before staging paper orders. Current run mode: <strong>{selectedSource}</strong>.
      <div>A good run keeps risk controls deterministic, preserves source coherence, and shows explainable approval/rejection outcomes at each step.</div>
    </Card>
    {!authReady ? <Card title="Auth status">Initializing authenticated session before replay data requests.</Card> : null}
    <Card>
      <div className="op-row">
        <button onClick={() => void runReplay()} disabled={busy}>{busy ? "Running…" : "Run replay"}</button>
        <button onClick={() => void loadRuns()} disabled={busy}>{busy ? "Refreshing…" : "Refresh runs"}</button>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadRuns()} />
    </Card>
    {error ? <ErrorState title="Replay unavailable" hint={error} /> : null}
    {stepError ? <ErrorState title="Replay steps unavailable" hint={stepError} /> : null}
    {runs.length === 0 && !error ? <EmptyState title="No replay runs yet" hint="Run replay to generate deterministic operator history." /> : null}
    <div className="op-grid-2">
      <Card title="Replay runs">
        <table className="op-table">
          <thead><tr><th>created_at</th><th>symbol</th><th>recs</th><th>approved</th><th>fills</th><th>ending_heat</th><th>ending_open_notional</th></tr></thead>
          <tbody>{runs.map((r) => <tr key={r.id} onClick={() => void loadSteps(r.id)} className={`is-selectable ${r.id === selectedRunId ? "is-active" : ""}`}><td>{r.created_at}</td><td>{r.symbol}</td><td>{r.recommendation_count}</td><td>{r.approved_count}</td><td>{r.fill_count}</td><td>{r.ending_heat}</td><td>{r.ending_open_notional}</td></tr>)}</tbody>
        </table>
      </Card>
      <Card title="Step timeline detail">
        {!selected ? <EmptyState title="Select a replay run" hint="Choose a row to inspect approved vs rejected path and heat snapshots." /> : <>
          <div style={{ marginBottom: 8 }}><strong>Run #{selected.id}</strong> · {selected.symbol} · source {selectedSource}</div>

          {/* Pass/fail summary bar */}
          {steps.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#9fb0c3", marginBottom: 3 }}>
                <span>approved {approvedCount}</span>
                <span>rejected {rejectedCount}</span>
                <span>fills {selected.fill_count}</span>
                <span>heat {selected.ending_heat}</span>
              </div>
              <div style={{ display: "flex", height: 10, borderRadius: 4, overflow: "hidden", background: "#2a3445" }}>
                {approvedCount > 0 && <div style={{ flex: approvedCount, background: "#4caf50" }} />}
                {rejectedCount > 0 && <div style={{ flex: rejectedCount, background: "#f44336" }} />}
              </div>
            </div>
          )}

          {/* Equity curve */}
          {equitySvg && (
            <div className="op-card" style={{ marginBottom: 8, padding: 8 }}>
              <div style={{ fontSize: 11, color: "#9fb0c3", marginBottom: 2 }}>Equity curve (post-step)</div>
              {equitySvg}
            </div>
          )}

          {/* Expandable step rows */}
          {guidedState.guided ? (
            <div className="op-row" style={{ marginBottom: 8 }}>
              <button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button>
            </div>
          ) : null}
          <div style={{ display: "grid", gap: 6 }}>
            {steps.map((s) => (
              <div
                key={s.id}
                className="op-card"
                style={{ padding: 8, cursor: "pointer" }}
                onClick={() => setExpandedStepId(expandedStepId === s.id ? null : s.id)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <strong>Step {s.step_index}</strong>
                  <StatusBadge tone={s.approved ? "good" : "warn"}>{s.approved ? "approved" : "rejected"}</StatusBadge>
                  <span style={{ fontSize: 11, color: "#9fb0c3" }}>
                    heat {String(s.post_step_snapshot.current_heat ?? "—")} · notional {String(s.post_step_snapshot.open_positions_notional ?? "—")}
                  </span>
                  <span style={{ marginLeft: "auto", fontSize: 11, color: "#9fb0c3" }}>{expandedStepId === s.id ? "▲ collapse" : "▼ expand"}</span>
                </div>
                {(expandedStepId === s.id && (!guidedState.guided || showOperatorDetail)) && (
                  <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 1fr", gap: 4, fontSize: "0.75rem", color: "var(--op-muted, #7a8999)", marginBottom: 4, padding: "0 0 4px 0", borderBottom: "1px solid var(--op-border, #1e2d3d)" }}>
                      <span>field</span><span>pre-step</span><span>post-step</span>
                    </div>
                    <SnapshotRow label="equity" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="equity" />
                    <SnapshotRow label="cash" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="cash" />
                    <SnapshotRow label="heat" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="current_heat" />
                    <SnapshotRow label="open notional" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="open_positions_notional" />
                    <SnapshotRow label="realized P&L" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="realized_pnl" />
                    <SnapshotRow label="open positions" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="open_position_count" digits={0} />
                    <SnapshotRow label="total fills" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="total_fills" digits={0} />
                    {s.post_step_snapshot.rejection_reason ? (
                      <div style={{ marginTop: 6, fontSize: "0.82rem", color: "var(--op-warn, #f2a03f)" }}>
                        rejection: {String(s.post_step_snapshot.rejection_reason)}
                      </div>
                    ) : null}
                    <div style={{ marginTop: 6, fontSize: "0.75rem", color: "var(--op-muted, #7a8999)" }}>
                      rec id: <span style={{ fontFamily: "monospace" }}>{s.recommendation_id}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {steps.length === 0 && <EmptyState title="No steps" hint="Steps load after selecting a run row." />}
        </>}
      </Card>
    </div>
  </section>;
}
