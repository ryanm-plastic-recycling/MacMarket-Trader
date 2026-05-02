"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { MetricLabel } from "@/components/ui/metric-help";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, parseGuidedFlowState } from "@/lib/guided-workflow";
import { WorkflowBanner } from "@/components/workflow-banner";
import { pickReplayRunSelection } from "@/lib/workflow-selection";
import { formatLineageBreadcrumb } from "@/lib/lineage-format";

<<<<<<< ours
type Run = {
  id: number;
  symbol: string;
  created_at: string;
  recommendation_count: number;
  approved_count: number;
  fill_count: number;
  ending_heat: number;
  ending_open_notional: number;
  market_data_source?: string;
  fallback_mode?: boolean | null;
  source_recommendation_id?: string | null;
  source_strategy?: string | null;
  has_stageable_candidate?: boolean;
  stageable_recommendation_id?: string | null;
  stageable_reason?: string | null;
  estimated_entry_fee?: number | null;
  estimated_exit_fee?: number | null;
  estimated_total_fees?: number | null;
  projected_gross_pnl?: number | null;
  projected_net_pnl?: number | null;
  fee_model?: string | null;
};
=======
type Run = { id: number; symbol: string; created_at: string; recommendation_count: number; approved_count: number; fill_count: number; ending_heat: number; ending_open_notional: number; market_data_source?: string; fallback_mode?: boolean | null; source_recommendation_id?: string | null; source_strategy?: string | null; has_stageable_candidate?: boolean; stageable_recommendation_id?: string | null; stageable_reason?: string | null };
>>>>>>> theirs
type RunDetail = Run & { source_recommendation_id?: string | null; source_strategy?: string | null; source_market_mode?: string | null; thesis?: string | null; key_levels?: { entry?: Record<string, unknown> | null; invalidation?: Record<string, unknown> | null; targets?: Record<string, unknown> | null } | null; summary_metrics?: Record<string, number> | null };
type Step = { id: number; step_index: number; recommendation_id: string; approved: boolean; rejection_reason?: string | null; thesis?: string | null; entry?: Record<string, unknown> | null; invalidation?: Record<string, unknown> | null; targets?: Record<string, unknown> | null; quality?: number | null; confidence?: number | null; pre_step_snapshot: Record<string, unknown>; post_step_snapshot: Record<string, unknown>; timestamp?: string | null; event_text?: string | null };
type ActiveRecommendation = { recommendation_id: string; display_id?: string; symbol: string; payload?: { thesis?: string; entry?: Record<string, unknown> | null; invalidation?: Record<string, unknown> | null; targets?: Record<string, unknown> | null; workflow?: { source_strategy?: string } } };

// Phase 6 close-out follow-up — Section 5: format the step timestamp into a
// short operator-readable form. Falls through to the raw string on parse
// failure so we never hide data we couldn't pretty-print.
function fmtStepTimestamp(value: string | null | undefined): string {
  if (!value) return "";
  const t = Date.parse(value);
  if (!Number.isFinite(t)) return String(value);
  const d = new Date(t);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mi = String(d.getUTCMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

function fmt(v: unknown, digits = 2): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toFixed(digits);
}
function fmtLevelRange(entry?: Record<string, unknown> | null): string {
  if (!entry) return "—";
  return `${fmt(entry.zone_low ?? entry.low)} - ${fmt(entry.zone_high ?? entry.high)}`;
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
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [activeRecommendation, setActiveRecommendation] = useState<ActiveRecommendation | null>(null);
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
  const unsupportedGuidedMode = Boolean(guidedState.guided && guidedState.marketMode && guidedState.marketMode !== "equities");

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

    const requestedSymbol = new URLSearchParams(searchKey).get("symbol");
    const requestedRun = new URLSearchParams(searchKey).get("replay_run");
    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");

    setRuns(result.items);
    setSelectedRunId((prev) => prev ?? pickReplayRunSelection({
      guided: guidedState.guided,
      requestedRunId: requestedRun,
      requestedRecommendationId: requestedRecommendation,
      requestedSymbol,
      runs: result.items,
    }));
    setError(null);
    setStepError(null);
    setFeedback({ state: "success", message: "Replay runs updated." });
    setBusy(false);
  }

  async function runReplay() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Authentication still initializing." });
      return;
    }
    setStatus("running replay...");
    setBusy(true);
    const preferredSymbol = new URLSearchParams(searchKey).get("symbol") ?? selected?.symbol ?? activeRecommendation?.symbol ?? guidedState.symbol;
    if (!preferredSymbol) {
      setError("Select a symbol or pass recommendation lineage before running replay.");
      setBusy(false);
      return;
    }
    const body: Record<string, unknown> = { symbol: preferredSymbol, market_mode: guidedState.marketMode ?? "equities" };
    if (guidedState.guided) {
      body.guided = true;
      if (guidedState.recommendationId) body.recommendation_id = guidedState.recommendationId;
      if (guidedState.strategy) body.strategy = guidedState.strategy;
    }
    const run = await fetchWorkflowApi<{
      id: number;
      market_data_source?: string;
      fallback_mode?: boolean;
      summary_metrics?: Record<string, number>;
      thesis?: string;
      key_levels?: Record<string, unknown>;
      estimated_entry_fee?: number | null;
      estimated_exit_fee?: number | null;
      estimated_total_fees?: number | null;
      projected_gross_pnl?: number | null;
      projected_net_pnl?: number | null;
      fee_model?: string | null;
    }>(
      "/api/user/replay-runs",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    );
    if (!run.ok) {
      const message = run.status === 503
        ? "Configured provider unavailable. Replay is blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (run.error ?? "Replay failed.");
      setError(message);
      setStatus("failed");
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }

    const fallbackMode = run.data?.fallback_mode ?? false;
    const sourceName = run.data?.market_data_source ?? "provider";
    const newRunId = run.data?.id ?? null;
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    setStatus("replay complete");
    setFeedback({ state: "success", message: "Replay run completed." });
    setSelectedRunId(newRunId);
    setRunDetail(run.data ? {
      id: run.data.id,
      symbol: preferredSymbol,
      created_at: new Date().toISOString(),
      recommendation_count: Number(run.data.summary_metrics?.recommendation_count ?? 0),
      approved_count: Number(run.data.summary_metrics?.approved_count ?? 0),
      fill_count: Number(run.data.summary_metrics?.fill_count ?? 0),
      ending_heat: Number(run.data.summary_metrics?.ending_heat ?? 0),
      ending_open_notional: Number(run.data.summary_metrics?.ending_open_notional ?? 0),
      market_data_source: sourceName,
      fallback_mode: fallbackMode,
      source_recommendation_id: guidedState.recommendationId,
      source_strategy: guidedState.strategy,
      thesis: typeof run.data.thesis === "string" ? run.data.thesis : null,
      key_levels: run.data.key_levels as RunDetail["key_levels"],
      summary_metrics: run.data.summary_metrics as Record<string, number> | null,
      estimated_entry_fee: run.data.estimated_entry_fee ?? null,
      estimated_exit_fee: run.data.estimated_exit_fee ?? null,
      estimated_total_fees: run.data.estimated_total_fees ?? null,
      projected_gross_pnl: run.data.projected_gross_pnl ?? null,
      projected_net_pnl: run.data.projected_net_pnl ?? null,
      fee_model: run.data.fee_model ?? null,
    } : null);

    const query = buildGuidedQuery({
      ...guidedState,
      symbol: preferredSymbol,
      source: sourceName,
      replayRunId: newRunId != null ? String(newRunId) : guidedState.replayRunId,
    });
    router.replace(`/replay-runs?${query}`);
    await loadRuns();
    if (newRunId != null) await loadSteps(newRunId, { autoExpandFirst: guidedState.guided });
    setBusy(false);

    // Auto-advance: in guided mode the operator's next step is Paper Order.
    // Skip if the replay produced no stageable candidate so the warning block stays visible.
    if (guidedState.guided && newRunId != null) {
      const detail = await fetchWorkflowApi<{ has_stageable_candidate?: boolean }>(
        `/api/user/replay-runs/${newRunId}`,
      );
      const blocked = detail.ok && detail.data?.has_stageable_candidate === false;
      if (!blocked) {
        const nextQuery = buildGuidedQuery({
          ...guidedState,
          symbol: preferredSymbol,
          source: sourceName,
          recommendationId: guidedState.recommendationId,
          replayRunId: String(newRunId),
        });
        setTimeout(() => router.push(`/orders?${nextQuery}`), 600);
      }
    }
  }

  function openOrdersNextAction() {
    const query = buildGuidedQuery({
      guided: guidedState.guided,
      symbol: selected?.symbol ?? guidedState.symbol,
      strategy: runDetail?.source_strategy ?? selected?.source_strategy ?? guidedState.strategy,
      marketMode: guidedState.marketMode ?? "equities",
      source: selectedSource,
      recommendationId: selected?.source_recommendation_id ?? runDetail?.source_recommendation_id ?? guidedState.recommendationId,
      replayRunId: selectedRunId != null ? String(selectedRunId) : guidedState.replayRunId,
    });
    router.push(`/orders?${query}`);
  }

  async function loadSteps(runId: number, options?: { autoExpandFirst?: boolean }) {
    if (!authReady) return;
    setSelectedRunId(runId);
    setBusy(true);
    setStepError(null);
    const result = await fetchWorkflowApi<Step>(`/api/user/replay-runs/${runId}/steps`);
    if (!result.ok) {
      const message = result.status === 503
        ? "Configured provider unavailable. Replay steps are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Unable to load run steps.");
      setStepError(message);
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }
    setSteps(result.items);
    if (options?.autoExpandFirst && result.items.length > 0) setExpandedStepId(result.items[0].id);
    const detail = await fetchWorkflowApi<RunDetail>(`/api/user/replay-runs/${runId}`);
    if (detail.ok) setRunDetail(detail.data ?? null);
    setBusy(false);
  }

  useEffect(() => {
    if (!authReady) return;
    void loadRuns();
  }, [searchKey, authReady]);

  useEffect(() => {
    if (!selectedRunId || !authReady) return;
    void loadSteps(selectedRunId);
  }, [selectedRunId, authReady]);

  useEffect(() => {
    if (!authReady || !guidedState.recommendationId) return;
    void (async () => {
      const recs = await fetchWorkflowApi<ActiveRecommendation>("/api/user/recommendations");
      if (!recs.ok) return;
      setActiveRecommendation(recs.items.find((item) => item.recommendation_id === guidedState.recommendationId) ?? null);
    })();
  }, [authReady, guidedState.recommendationId]);

  // Phase 6 close-out follow-up — Section 4: in guided mode only, derive
  // "has the operator already run replay for the active recommendation?" so
  // the CTA can shift between pulsing primary (action needed) and a calm
  // secondary "Run again →". Explorer/non-guided mode keeps the primary CTA
  // styling unchanged so existing flows and tests are not perturbed.
  const replayDoneForRec = guidedState.guided
    ? Boolean(selectedRunId) || runs.some((r) => r.source_recommendation_id && r.source_recommendation_id === guidedState.recommendationId)
    : false;

  const approvedCount = steps.filter((s) => s.approved).length;
  const rejectedCount = steps.length - approvedCount;
  const equityPoints = steps.map((s) => Number(s.post_step_snapshot?.equity ?? 0)).filter((v) => v > 0);
  const distinctEquityCount = new Set(equityPoints).size;
  const equitySvg = (() => {
    if (equityPoints.length < 2 || distinctEquityCount < 2) return null;
    const W = 280; const H = 52; const pad = 4;
    const minV = Math.min(...equityPoints);
    const maxV = Math.max(...equityPoints);
    const range = maxV - minV || 1;
    const pts = equityPoints.map((v, i) => {
      const x = pad + (i / (equityPoints.length - 1)) * (W - pad * 2);
      const y = H - pad - ((v - minV) / range) * (H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const stroke = equityPoints[equityPoints.length - 1] >= equityPoints[0] ? "#4caf50" : "#f44336";
    return <svg width={W} height={H}><polyline points={pts} fill="none" stroke={stroke} strokeWidth="2" /></svg>;
  })();

  return <section className="op-stack">
    <PageHeader title="Replay workspace" subtitle="Step 3 action page: run deterministic replay from recommendation context and inspect step-by-step risk transitions." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <WorkflowBanner
      current="Replay"
      state={{
        ...guidedState,
        symbol: selected?.symbol ?? activeRecommendation?.symbol ?? guidedState.symbol,
        strategy: runDetail?.source_strategy ?? selected?.source_strategy ?? activeRecommendation?.payload?.workflow?.source_strategy ?? guidedState.strategy,
        source: selected?.market_data_source ?? selectedSource,
        recommendationId: selected?.source_recommendation_id ?? runDetail?.source_recommendation_id ?? guidedState.recommendationId,
        replayRunId: selectedRunId != null ? String(selectedRunId) : guidedState.replayRunId,
      }}
      backHref="/recommendations"
      backLabel="Back to Recommendation"
      nextHref="/orders"
      nextLabel="Go to Paper Order step"
      nextDisabled={guidedState.guided && (!guidedState.recommendationId || !selectedRunId)}
      nextDisabledReason="Guided orders require both persisted recommendation and replay run lineage."
      compact={!guidedState.guided}
    />
    {guidedState.guided ? <Card title="Guided flow progress"><GuidedStepRail current="Replay" /></Card> : null}
    {guidedState.guided ? <Card title="Next action"><div>Go to the paper-order step after replay results are reviewed.</div><div className="op-row" style={{ marginTop: 8 }}><button onClick={openOrdersNextAction} disabled={unsupportedGuidedMode}>Go to Paper Order step</button></div></Card> : null}

    <Card title="What replay is for">
      Use replay to validate whether a recommendation logic path behaves consistently before staging paper orders. Current run mode: <strong>{selectedSource}</strong>.
      <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)" }}>Arriving here does not create a replay run.</div>
    </Card>
    <Card title="Workflow lineage">
      <div>{formatLineageBreadcrumb(guidedState, {
        symbol: selected?.symbol ?? activeRecommendation?.symbol ?? guidedState.symbol,
        strategy: runDetail?.source_strategy ?? selected?.source_strategy ?? activeRecommendation?.payload?.workflow?.source_strategy ?? guidedState.strategy,
        recommendationId: selected?.source_recommendation_id ?? runDetail?.source_recommendation_id ?? guidedState.recommendationId,
        recommendationDisplayId: activeRecommendation?.display_id ?? null,
        replayRunId: selectedRunId ?? guidedState.replayRunId,
        orderId: guidedState.orderId,
      })}</div>
    </Card>

    {guidedState.guided ? (
      <Card title="Replaying recommendation">
        <div><strong>symbol:</strong> {runDetail?.symbol ?? selected?.symbol ?? activeRecommendation?.symbol ?? guidedState.symbol ?? "—"} · <strong>strategy:</strong> {runDetail?.source_strategy ?? guidedState.strategy ?? "—"}</div>
        <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{runDetail?.source_recommendation_id ?? selected?.source_recommendation_id ?? guidedState.recommendationId ?? "—"}</span> · <strong>replay run id:</strong> <span style={{ fontFamily: "monospace" }}>{selectedRunId ?? "—"}</span></div>
        {(runDetail?.thesis ?? activeRecommendation?.payload?.thesis) ? <div><strong>thesis:</strong> {runDetail?.thesis ?? activeRecommendation?.payload?.thesis}</div> : null}
        {runDetail?.estimated_total_fees != null ? (
          <div style={{ marginTop: 8, padding: 10, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
            <div style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Estimated paper-only round trip (entry + exit)</div>
            <div><strong><MetricLabel label="Fees" term="equity_commission_per_trade" />:</strong> ${runDetail.estimated_total_fees.toFixed(2)} ({runDetail.fee_model ?? "equity_per_trade"})</div>
            <div><strong>Entry fee:</strong> ${runDetail.estimated_entry_fee?.toFixed(2) ?? "0.00"} · <strong>Exit fee:</strong> ${runDetail.estimated_exit_fee?.toFixed(2) ?? "0.00"}</div>
            <div>
              <strong><MetricLabel label="Projected net outcome" term="net_pnl" />:</strong>{" "}
              {runDetail.projected_net_pnl != null ? `${runDetail.projected_net_pnl >= 0 ? "+" : ""}${runDetail.projected_net_pnl.toFixed(2)}` : "Unavailable"}
            </div>
            {runDetail.projected_gross_pnl != null ? (
              <div style={{ color: "var(--op-muted, #7a8999)" }}>
                <MetricLabel label="Gross P&L" term="gross_pnl" /> {runDetail.projected_gross_pnl >= 0 ? "+" : ""}{runDetail.projected_gross_pnl.toFixed(2)} using existing recommendation levels.
              </div>
            ) : (
              <div style={{ color: "var(--op-muted, #7a8999)" }}>
                Fees are estimated even when a gross projection is not safe to derive.
              </div>
            )}
          </div>
        ) : null}
        {!selected && guidedState.recommendationId ? (
          <div className="op-card" style={{ marginTop: 10, padding: 12 }}>
            <h3 style={{ margin: "0 0 6px 0" }}>No replay run yet for this recommendation</h3>
            <div><strong>symbol:</strong> {activeRecommendation?.symbol ?? guidedState.symbol ?? "—"} · <strong>strategy:</strong> {guidedState.strategy ?? "—"}</div>
            <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{guidedState.recommendationId}</span></div>
            <div><strong>thesis:</strong> {activeRecommendation?.payload?.thesis ?? "—"}</div>
            <div><strong>entry:</strong> {JSON.stringify(activeRecommendation?.payload?.entry ?? {})}</div>
            <div><strong>invalidation:</strong> {JSON.stringify(activeRecommendation?.payload?.invalidation ?? {})}</div>
            <div><strong>targets:</strong> {JSON.stringify(activeRecommendation?.payload?.targets ?? {})}</div>
            <button className="op-btn-primary-cta op-btn-pulse" style={{ marginTop: 8, width: "100%" }} onClick={() => void runReplay()} disabled={busy || unsupportedGuidedMode}>{busy ? "Running…" : "Run replay now →"}</button>
          </div>
        ) : null}
      </Card>
    ) : null}

<<<<<<< ours
    <Card><div className="op-row"><button className={replayDoneForRec ? "op-btn op-btn-secondary" : "op-btn-primary-cta op-btn-pulse"} onClick={() => void runReplay()} disabled={busy || unsupportedGuidedMode}>{busy ? "Running…" : replayDoneForRec ? "Run again →" : "Run replay now →"}</button><button onClick={openOrdersNextAction} disabled={!selected?.has_stageable_candidate || unsupportedGuidedMode}>Go to Paper Order step</button><button onClick={() => void loadRuns()} disabled={busy}>{busy ? "Refreshing…" : "Refresh runs"}</button></div><InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadRuns()} /></Card>
=======
    <Card><div className="op-row"><button onClick={() => void runReplay()} disabled={busy || unsupportedGuidedMode}>{busy ? "Running…" : "Run replay now"}</button><button onClick={openOrdersNextAction} disabled={!selected?.has_stageable_candidate || unsupportedGuidedMode}>Go to Paper Order step</button><button onClick={() => void loadRuns()} disabled={busy}>{busy ? "Refreshing…" : "Refresh runs"}</button></div><InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadRuns()} /></Card>
>>>>>>> theirs
    {error ? <ErrorState title="Replay unavailable" hint={error} /> : null}
    {stepError ? <ErrorState title="Replay steps unavailable" hint={stepError} /> : null}

    <div className="op-grid-2">
      <Card title={guidedState.guided ? "Replay history (secondary)" : "Replay runs"}>
        {guidedState.guided ? <div style={{ marginBottom: 6, color: "var(--op-muted, #7a8999)" }}>Secondary panel: full replay history</div> : null}
<<<<<<< ours
        <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
        <table className="op-table" style={{ marginTop: guidedState.guided ? 8 : 0 }}>
          <thead><tr><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>created_at</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>paths</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>approved</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>fills</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>stageable</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>ending_heat</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>ending_open_notional</th></tr></thead>
          <tbody>
            {runs.length === 0 && !busy ? <tr><td colSpan={8} style={{ color: "#9fb0c3", textAlign: "center", padding: "16px 8px" }}>No replay runs yet. Click "Run replay now" above to run your first replay.</td></tr> : null}
            {runs.map((r) => <tr key={r.id} onClick={() => void loadSteps(r.id)} className={`is-selectable ${r.id === selectedRunId ? "is-active" : ""}`}><td>{r.created_at}</td><td>{r.symbol}</td><td>{r.recommendation_count}</td><td>{r.approved_count}</td><td>{r.fill_count}</td><td>{r.has_stageable_candidate ? "yes" : "no"}</td><td>{r.ending_heat}</td><td>{r.ending_open_notional}</td></tr>)}
          </tbody>
=======
        <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
        <table className="op-table" style={{ marginTop: guidedState.guided ? 8 : 0 }}>
          <thead><tr><th>created_at</th><th>symbol</th><th>paths</th><th>approved</th><th>fills</th><th>stageable</th><th>ending_heat</th><th>ending_open_notional</th></tr></thead>
          <tbody>{runs.map((r) => <tr key={r.id} onClick={() => void loadSteps(r.id)} className={`is-selectable ${r.id === selectedRunId ? "is-active" : ""}`}><td>{r.created_at}</td><td>{r.symbol}</td><td>{r.recommendation_count}</td><td>{r.approved_count}</td><td>{r.fill_count}</td><td>{r.has_stageable_candidate ? "yes" : "no"}</td><td>{r.ending_heat}</td><td>{r.ending_open_notional}</td></tr>)}</tbody>
>>>>>>> theirs
        </table>
        </div>
      </Card>

      <Card title="Step timeline detail">
        {!selected ? <EmptyState title="Select a replay run" hint="Choose a row to inspect approved vs rejected path and heat snapshots." /> : <>
          <div style={{ marginBottom: 8 }}><strong>Run #{selected.id}</strong> · {selected.symbol} · source {selectedSource}</div>
<<<<<<< ours
          {runDetail?.estimated_total_fees != null ? (
            <div className="op-card" style={{ marginBottom: 8, padding: 10 }}>
              <div style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Estimated paper-only stageable candidate preview (entry + exit)</div>
              <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}><MetricLabel label="Fees" term="equity_commission_per_trade" /> · <MetricLabel label="Projected net" term="net_pnl" /></div>
              <div><strong>Fees:</strong> ${runDetail.estimated_total_fees.toFixed(2)} · <strong>Projected net:</strong> {runDetail.projected_net_pnl != null ? `${runDetail.projected_net_pnl >= 0 ? "+" : ""}${runDetail.projected_net_pnl.toFixed(2)}` : "Unavailable"}</div>
            </div>
          ) : null}
          {selected.has_stageable_candidate === false ? (
            <div className="op-error" style={{ marginBottom: 8 }}>
              <strong>Replay produced no stageable candidate</strong>
              <p>{selected.stageable_reason ?? "No fills occurred or no recommendation met approval thresholds."}</p>
              <p>Return to Recommendations to select a different rec, or run a new replay.</p>
            </div>
          ) : null}
=======
          {selected.has_stageable_candidate === false ? <div className="op-card" style={{ marginBottom: 8, padding: 8 }}>Replay completed, but no stageable path was approved.</div> : null}
>>>>>>> theirs
          {selected.approved_count === 0 && selected.fill_count === 0 ? <div className="op-card" style={{ marginBottom: 8, padding: 8 }}>Replay completed, but no fills occurred. Portfolio remained unchanged.</div> : null}
          {steps.length > 0 && <div style={{ marginBottom: 10 }}><div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#9fb0c3", marginBottom: 3 }}><span>approved {approvedCount}</span><span>rejected {rejectedCount}</span><span>fills {selected.fill_count}</span></div></div>}
          {equitySvg ? <div className="op-card" style={{ marginBottom: 8, padding: 8 }}><div style={{ fontSize: 11, color: "#9fb0c3", marginBottom: 2 }}>Equity curve (post-step)</div>{equitySvg}</div> : null}
          {steps.length > 0 ? (
            <div className="op-card" style={{ marginBottom: 8, padding: 10, fontSize: 13, lineHeight: 1.5, color: "var(--op-muted, #9fb0c3)" }}>
              Each row shows one bar of historical data the replay engine evaluated.{" "}
              <span style={{ color: "#21c06e", fontWeight: 600 }}>✓ approved</span> means the recommendation logic would have triggered.{" "}
              <span style={{ color: "#e07a7a", fontWeight: 600 }}>✗ rejected</span> means the bar did not meet the strategy gate.
              Approved bars contribute to fill simulation.
            </div>
          ) : null}
          {guidedState.guided ? <div className="op-row" style={{ marginBottom: 8 }}><button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button></div> : null}
          <div style={{ display: "grid", gap: 6 }}>
            {steps.map((s) => {
              const tsLabel = fmtStepTimestamp(s.timestamp);
              const statusIcon = s.approved ? "✓" : "✗";
              const statusColor = s.approved ? "#21c06e" : "#e07a7a";
              return <div key={s.id} className={`op-card ${s.approved ? "is-approved" : "is-rejected"}`} style={{ padding: 8, cursor: "pointer", borderLeft: s.approved === true ? "3px solid #21c06e" : s.approved === false ? "3px solid #f44336" : undefined }} onClick={() => setExpandedStepId(expandedStepId === s.id ? null : s.id)}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: statusColor, fontWeight: 700, fontSize: 14 }}>{statusIcon}</span>
                <strong>Bar #{s.step_index + 1}</strong>
                {tsLabel ? <span style={{ color: "var(--op-muted, #9fb0c3)", fontSize: 12 }}>· {tsLabel}</span> : null}
                <StatusBadge tone={s.approved ? "good" : "warn"}>{s.approved ? "approved" : "rejected"}</StatusBadge>
                <span style={{ marginLeft: "auto", fontSize: 11, color: "#9fb0c3" }}>{expandedStepId === s.id ? "▲ collapse" : "▼ expand"}</span>
              </div>
              {s.event_text ? <div style={{ marginTop: 4, fontSize: 12, color: "var(--op-muted, #9fb0c3)" }}>Event: {s.event_text}</div> : null}
              {expandedStepId === s.id ? <div style={{ marginTop: 8 }}>
                <div>{s.rejection_reason ? <><strong>rejection reason:</strong> {String(s.rejection_reason)}</> : <strong>verdict:</strong>} {s.approved ? "Approved" : "Rejected"}</div>
                {s.thesis ? <div><strong>thesis:</strong> {s.thesis}</div> : null}
                <div><strong>entry zone:</strong> {fmtLevelRange(s.entry)}</div>
                <div><strong>stop / invalidation:</strong> {fmt((s.invalidation as Record<string, unknown> | null | undefined)?.["price"])} {(s.invalidation as Record<string, unknown> | null | undefined)?.["reason"] ? `(${String((s.invalidation as Record<string, unknown>)["reason"])})` : ""}</div>
                <div><strong>targets:</strong> T1 {fmt((s.targets as Record<string, unknown> | null | undefined)?.["target_1"])} · T2 {fmt((s.targets as Record<string, unknown> | null | undefined)?.["target_2"])}</div>
<<<<<<< ours
                {(s.quality != null || s.confidence != null) ? (
                  <div><strong><MetricLabel label="Score" term="score" />:</strong> {fmt(s.quality)} · <strong><MetricLabel label="Confidence" term="confidence" />:</strong> {fmt(s.confidence)}</div>
                ) : null}
=======
>>>>>>> theirs
                <details style={{ marginTop: 6 }}>
                  <summary>Raw operator detail</summary>
                  <div><strong>entry:</strong> {JSON.stringify(s.entry ?? {})}</div>
                  <div><strong>invalidation:</strong> {JSON.stringify(s.invalidation ?? {})}</div>
                  <div><strong>targets:</strong> {JSON.stringify(s.targets ?? {})}</div>
                </details>
                <div style={{ marginTop: 6, fontSize: "0.75rem", color: "var(--op-muted, #7a8999)" }}>rec id: <span style={{ fontFamily: "monospace" }}>{s.recommendation_id}</span></div>
                {(!guidedState.guided || showOperatorDetail) ? <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: "0.82rem" }}><strong>Show operator detail</strong></div>
                  <SnapshotRow label="equity" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="equity" />
                  <SnapshotRow label="heat" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="current_heat" />
                  <SnapshotRow label="open notional" pre={s.pre_step_snapshot} post={s.post_step_snapshot} field="open_positions_notional" />
                </div> : null}
              </div> : null}
            </div>;
            })}
          </div>
          {steps.length === 0 ? <EmptyState title="No steps" hint="Steps load after selecting a run row." /> : null}
        </>}
      </Card>
    </div>
  </section>;
}
