"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type Run = { id: number; symbol: string; created_at: string; recommendation_count: number; approved_count: number; fill_count: number; ending_heat: number; ending_open_notional: number; market_data_source?: string; fallback_mode?: boolean | null };
type Step = { id: number; step_index: number; recommendation_id: string; approved: boolean; pre_step_snapshot: any; post_step_snapshot: any };

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("workflow pending");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const selected = useMemo(() => runs.find((r) => r.id === selectedRunId) ?? null, [runs, selectedRunId]);
  const selectedSource = selected ? (selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? "provider")) : dataSource;

  async function loadRuns() {
    if (!isLoaded || !isSignedIn) {
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
    setSelectedRunId((prev) => prev ?? result.items.find((run) => run.symbol === requestedSymbol)?.id ?? result.items[0]?.id ?? null);
    setBusy(false);
  }

  async function runReplay() {
    if (!isLoaded || !isSignedIn) {
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
    await loadRuns();
    setBusy(false);
  }

  async function loadSteps(runId: number) {
    if (!isLoaded || !isSignedIn) return;
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
    if (!isLoaded || !isSignedIn) return;
    void loadRuns();
  }, [searchKey, isLoaded, isSignedIn]);
  useEffect(() => { if (selectedRunId && isLoaded && isSignedIn) void loadSteps(selectedRunId); }, [selectedRunId, isLoaded, isSignedIn]);
  useEffect(() => {
    if (feedback.state !== "success") return;
    const timer = window.setTimeout(() => setFeedback({ state: "idle", message: "" }), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback.state, feedback.message]);

  const timelinePoints = steps.map((step) => ({
    step: step.step_index,
    pre: Number(step.pre_step_snapshot?.open_positions_notional ?? 0),
    post: Number(step.post_step_snapshot?.open_positions_notional ?? 0),
    pnlDelta: Number(step.post_step_snapshot?.equity ?? 0) - Number(step.pre_step_snapshot?.equity ?? 0),
  }));

  return <section className="op-stack">
    <PageHeader title="Replay workspace" subtitle="Run deterministic replay from recommendation context and inspect step-by-step risk transitions." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <Card title="What replay is for">
      Use replay to validate whether a recommendation logic path behaves consistently before staging paper orders. Current run mode: <strong>{selectedSource}</strong>.
      <div>A good run keeps risk controls deterministic, preserves source coherence, and shows explainable approval/rejection outcomes at each step.</div>
    </Card>
    {!isLoaded ? <Card title="Auth status">Initializing authenticated session before replay data requests.</Card> : null}
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
          <div style={{ marginBottom: 8 }}><strong>Run #{selected.id}</strong> · {selected.symbol} · source {selectedSource} · recommendation {new URLSearchParams(searchKey).get("recommendation") ?? "linked from selected run"}</div>
          <div className="op-card" style={{ marginBottom: 8 }}>
            <strong>Validation scope</strong>
            <div>Originating setup/recommendation: {new URLSearchParams(searchKey).get("recommendation") ?? steps[0]?.recommendation_id ?? "selected run set"}.</div>
            <div>Validated: deterministic approvals, heat transitions, and order-intent eligibility under source {selectedSource}.</div>
          </div>
          <div className="op-card" style={{ marginBottom: 8 }}>
            <strong>Narrative summary</strong>
            <div>
              {selected.approved_count} / {selected.recommendation_count} recommendations approved, {selected.fill_count} fills,
              ending heat {selected.ending_heat}, ending open notional {selected.ending_open_notional}.
            </div>
          </div>
          <div style={{ display: "grid", gap: 8 }}>{steps.map((s) => <div key={s.id} className="op-card" style={{ padding: 8 }}>
            <strong>Step {s.step_index}</strong> <StatusBadge tone={s.approved ? "good" : "warn"}>{s.approved ? "approved" : "rejected"}</StatusBadge>
            <div>Recommendation: {s.recommendation_id}</div>
            <div>Pre heat/open notional: {s.pre_step_snapshot?.current_heat} / {s.pre_step_snapshot?.open_positions_notional}</div>
            <div>Post heat/open notional: {s.post_step_snapshot?.current_heat} / {s.post_step_snapshot?.open_positions_notional}</div>
          </div>)}</div>
          {timelinePoints.length > 0 ? <div className="op-card" style={{ marginTop: 8 }}>
            <strong>Entry vs exit notional timeline</strong>
            {timelinePoints.map((point) => <div key={point.step}>Step {point.step}: {point.pre} → {point.post} (equity Δ {point.pnlDelta.toFixed(2)})</div>)}
          </div> : null}
        </>}
      </Card>
    </div>
  </section>;
}
