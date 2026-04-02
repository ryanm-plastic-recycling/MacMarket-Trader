"use client";

import { useEffect, useMemo, useState } from "react";

import { Card, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalized } from "@/lib/api-client";

type Run = { id: number; symbol: string; created_at: string; recommendation_count: number; approved_count: number; fill_count: number; ending_heat: number; ending_open_notional: number };
type Step = { id: number; step_index: number; recommendation_id: string; approved: boolean; pre_step_snapshot: any; post_step_snapshot: any };

export default function Page() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("unknown");
  const selected = useMemo(() => runs.find((r) => r.id === selectedRunId) ?? null, [runs, selectedRunId]);

  async function loadRuns() {
    const result = await fetchNormalized<Run>("/api/user/replay-runs");
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setRuns(result.items);
    setSelectedRunId((prev) => prev ?? result.items[0]?.id ?? null);
  }

  async function runReplay() {
    setStatus("running replay...");
    const run = await fetchNormalized<{ id: number; market_data_source?: string; fallback_mode?: boolean }>("/api/user/replay-runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: selected?.symbol ?? "AAPL" }) });
    if (!run.ok) {
      setError(run.error ?? "Replay failed.");
      setStatus("failed");
      return;
    }
    const fallbackMode = run.data?.fallback_mode ?? false;
    const sourceName = run.data?.market_data_source ?? "provider";
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    setStatus("replay complete");
    await loadRuns();
  }

  async function loadSteps(runId: number) {
    setSelectedRunId(runId);
    const result = await fetchNormalized<Step>(`/api/user/replay-runs/${runId}/steps`);
    if (!result.ok) {
      setError(result.error ?? "Unable to load run steps.");
      return;
    }
    setSteps(result.items);
  }

  useEffect(() => { void loadRuns(); }, []);
  useEffect(() => { if (selectedRunId) void loadSteps(selectedRunId); }, [selectedRunId]);

  const timelinePoints = steps.map((step) => ({
    step: step.step_index,
    pre: Number(step.pre_step_snapshot?.open_positions_notional ?? 0),
    post: Number(step.post_step_snapshot?.open_positions_notional ?? 0),
    pnlDelta: Number(step.post_step_snapshot?.equity ?? 0) - Number(step.pre_step_snapshot?.equity ?? 0),
  }));

  return <section className="op-stack">
    <PageHeader title="Replay workspace" subtitle="Run deterministic replay from recommendation context and inspect step-by-step risk transitions." actions={<StatusBadge tone="neutral">{status}</StatusBadge>} />
    <Card title="What replay is for">
      Use replay to validate whether a recommendation logic path behaves consistently before staging paper orders. Current run mode: <strong>{dataSource}</strong>.
    </Card>
    <Card>
      <div className="op-row">
        <button onClick={() => void runReplay()}>Run replay</button>
        <button onClick={() => void loadRuns()}>Refresh runs</button>
      </div>
    </Card>
    {error ? <ErrorState title="Replay unavailable" hint={error} /> : null}
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
          <div style={{ marginBottom: 8 }}><strong>Run #{selected.id}</strong> · {selected.symbol}</div>
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
