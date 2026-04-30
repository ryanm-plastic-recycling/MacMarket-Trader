"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";

import Link from "next/link";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { MetricLabel } from "@/components/ui/metric-help";
import { fetchWorkflowApi } from "@/lib/api-client";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import { GuidedStepRail } from "@/components/guided-step-rail";
import { buildGuidedQuery, parseGuidedFlowState } from "@/lib/guided-workflow";
import { WorkflowBanner } from "@/components/workflow-banner";
import { pickOrderSelection } from "@/lib/workflow-selection";
import { PaperOptionsPositionsSection } from "@/components/orders/paper-options-positions-section";
import {
  canReopenTrade,
  formatHoldDuration,
  formatRelativeTime,
  pnlColor,
  reopenSecondsRemaining,
} from "@/lib/orders-helpers";
import { formatLineageBreadcrumb } from "@/lib/lineage-format";

type Order = {
  order_id: string;
  recommendation_id: string;
  replay_run_id?: number | null;
  symbol: string;
  status: string;
  side: string;
  shares: number;
  limit_price: number;
  created_at: string;
  canceled_at?: string | null;
  market_data_source?: string | null;
  fallback_mode?: boolean | null;
  estimated_entry_fee?: number | null;
  estimated_exit_fee?: number | null;
  estimated_total_fees?: number | null;
  projected_gross_pnl?: number | null;
  projected_net_pnl?: number | null;
  fee_model?: string | null;
  fills: Array<{ fill_price: number; filled_shares: number; timestamp: string }>;
};
type PortfolioSummary = { open_positions: number; total_open_notional: number; unrealized_pnl: number | null; realized_pnl: number; gross_realized_pnl: number; net_realized_pnl: number; total_commission_paid: number; closed_trade_count: number; win_rate: number | null; lifecycle_status?: string; notes?: string };
type CloseResult = { order_id: string; symbol: string; gross_pnl: number; net_pnl: number; commission_paid: number; realized_pnl: number; entry_price: number; close_price: number; shares: number };

type PaperPosition = {
  id: number;
  symbol: string;
  side: string;
  opened_qty: number;
  remaining_qty: number;
  avg_entry_price: number;
  open_notional: number;
  status: string;
  opened_at: string | null;
  closed_at: string | null;
  recommendation_id: string | null;
  replay_run_id: number | null;
  order_id: string | null;
  estimated_close_fee?: number | null;
  fee_model?: string | null;
};

type PaperTrade = {
  id: number;
  symbol: string;
  side: string;
  qty: number;
  entry_price: number;
  exit_price: number | null;
  gross_pnl: number;
  net_pnl: number;
  commission_paid: number;
  realized_pnl: number;
  opened_at: string | null;
  closed_at: string | null;
  hold_seconds: number | null;
  position_id: number | null;
  recommendation_id: string | null;
  replay_run_id: number | null;
  order_id: string | null;
  close_reason: string | null;
};

const CLOSE_REASONS = ["Target hit", "Stop hit", "Manual exit", "Time exit", "Other"] as const;

function formatSignedDollars(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function tradeDirectionMultiplier(side: string | null | undefined): number {
  const normalized = String(side ?? "").trim().toLowerCase();
  return normalized === "short" || normalized === "sell" ? -1 : 1;
}

function parseFiniteNumber(value: string): number | null {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function estimateClosePnl(params: {
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  side: string;
  estimatedCloseFee: number;
}): { gross: number; net: number } | null {
  const { entryPrice, exitPrice, quantity, side, estimatedCloseFee } = params;
  const values = [entryPrice, exitPrice, quantity, estimatedCloseFee];
  if (values.some((value) => !Number.isFinite(value))) return null;
  const gross = (exitPrice - entryPrice) * quantity * tradeDirectionMultiplier(side);
  return { gross, net: gross - estimatedCloseFee };
}

export default function Page() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const guidedState = useMemo(() => parseGuidedFlowState(searchParams), [searchParams]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [dataSource, setDataSource] = useState("workflow pending");
  const [busy, setBusy] = useState(false);
  const [showOperatorDetail, setShowOperatorDetail] = useState(false);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [portfolioSummary, setPortfolioSummary] = useState<PortfolioSummary | null>(null);
  const [replayOutcome, setReplayOutcome] = useState<{
    has_stageable_candidate: boolean;
    stageable_reason?: string | null;
    estimated_entry_fee?: number | null;
    estimated_exit_fee?: number | null;
    estimated_total_fees?: number | null;
    projected_gross_pnl?: number | null;
    projected_net_pnl?: number | null;
    fee_model?: string | null;
  } | null>(null);
  const [closeInputVisible, setCloseInputVisible] = useState(false);
  const [closePriceInput, setClosePriceInput] = useState("");
  const [closeResults, setCloseResults] = useState<Record<string, CloseResult>>({});
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [closingPositionId, setClosingPositionId] = useState<number | null>(null);
  const [closeMarkInput, setCloseMarkInput] = useState("");
  const [closeReasonInput, setCloseReasonInput] = useState<string>(CLOSE_REASONS[0]);
  // Pass 4 — Cancel staged order: which order_id is awaiting inline confirm.
  const [cancelingOrderId, setCancelingOrderId] = useState<string | null>(null);
  // Pass 4 — Reopen closed trade: which trade_id is awaiting inline confirm.
  const [reopeningTradeId, setReopeningTradeId] = useState<number | null>(null);
  // 30-second tick used to refresh the reopen-window countdown so stale rows
  // automatically lose their button when the 5-minute window closes.
  const [nowMs, setNowMs] = useState<number>(() => Date.now());
  // Pass 4 — display_id lookup for the workflow lineage card. Fetched once
  // per page mount; falls back to the auto-shortened "Rec #..." when missing.
  const [displayIdMap, setDisplayIdMap] = useState<Record<string, string>>({});
  const authReady = isLoaded && (isSignedIn || isE2EAuthBypassEnabled());
  const selected = useMemo(() => orders.find((o) => o.order_id === selectedOrderId) ?? null, [orders, selectedOrderId]);
  const selectedOpenPosition = useMemo(() => {
    if (!selected) return null;
    return (
      positions.find((position) => position.order_id === selected.order_id)
      ?? positions.find((position) => position.symbol === selected.symbol && position.side === selected.side)
      ?? null
    );
  }, [positions, selected]);
  const selectedClosePreview = useMemo(() => {
    if (!selected || !closeInputVisible) return null;
    const closePrice = parseFiniteNumber(closePriceInput);
    if (closePrice == null) return null;
    const entryPrice = selectedOpenPosition?.avg_entry_price ?? selected.fills[0]?.fill_price ?? selected.limit_price;
    const quantity = selectedOpenPosition?.remaining_qty ?? selected.shares;
    const estimatedCloseFee = selectedOpenPosition?.estimated_close_fee ?? selected.estimated_exit_fee ?? 0;
    return estimateClosePnl({
      entryPrice,
      exitPrice: closePrice,
      quantity,
      side: selected.side,
      estimatedCloseFee,
    });
  }, [closeInputVisible, closePriceInput, selected, selectedOpenPosition]);
  const unsupportedGuidedMode = Boolean(guidedState.guided && guidedState.marketMode && guidedState.marketMode !== "equities");
  const detailRef = useRef<HTMLDivElement | null>(null);

  // Phase 6 close-out follow-up — Section 4: in guided mode only, pulse the
  // Stage CTA when no order exists for the active rec/replay; calm
  // "Stage another →" once one is staged. Explorer/non-guided mode keeps the
  // primary CTA styling unchanged so existing flows and tests are not perturbed.
  const orderDoneForRec = guidedState.guided
    ? orders.some((o) => {
        const recMatch = guidedState.recommendationId ? o.recommendation_id === guidedState.recommendationId : false;
        const runMatch = guidedState.replayRunId ? String(o.replay_run_id ?? "") === guidedState.replayRunId : false;
        return recMatch || runMatch;
      })
    : false;

  async function load() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Initializing authenticated workflow…" });
      return;
    }
    setBusy(true);
    setError(null);
    setFeedback({ state: "loading", message: "Loading orders…" });
    const result = await fetchWorkflowApi<Order>("/api/user/orders");
    if (!result.ok) {
      const message = result.status === 503
        ? "Configured provider unavailable. Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Orders load failed.");
      setError(message);
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }

    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    const requestedOrder = new URLSearchParams(searchKey).get("order");
    const requestedReplayRun = new URLSearchParams(searchKey).get("replay_run");
    setOrders(result.items);
    setSelectedOrderId((prev) => prev ?? pickOrderSelection({
      guided: guidedState.guided,
      requestedOrderId: requestedOrder,
      requestedReplayRunId: requestedReplayRun,
      requestedRecommendationId: requestedRecommendation,
      orders: result.items,
    }));
    const firstSource = result.items[0]?.fallback_mode ? `fallback (${result.items[0]?.market_data_source ?? "provider"})` : (result.items[0]?.market_data_source ?? "provider");
    setDataSource(firstSource ?? "workflow pending");
    setFeedback({ state: "success", message: "Orders updated." });
    const summary = await fetchWorkflowApi<PortfolioSummary>("/api/user/orders/portfolio-summary");
    if (summary.ok) setPortfolioSummary(summary.data ?? null);
    setBusy(false);
  }

  async function stagePaperOrder() {
    if (!authReady) {
      setFeedback({ state: "loading", message: "Authentication still initializing." });
      return;
    }
    setStatus("staging paper order...");
    setBusy(true);
    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    const symbolHint = selected?.symbol ?? guidedState.symbol ?? null;
    const body: Record<string, unknown> = {};
    if (guidedState.guided && !requestedRecommendation) {
      setError("Guided order staging requires recommendation lineage.");
      setBusy(false);
      return;
    }
    if (requestedRecommendation) body.recommendation_id = requestedRecommendation;
    else if (symbolHint) body.symbol = symbolHint;
    else {
      setError("Provide symbol context for non-guided order staging.");
      setBusy(false);
      return;
    }

    body.market_mode = guidedState.marketMode ?? "equities";
    if (guidedState.guided) {
      body.guided = true;
      if (guidedState.replayRunId) body.replay_run_id = Number(guidedState.replayRunId);
    }

    const result = await fetchWorkflowApi<{
      order_id: string;
      market_data_source?: string;
      fallback_mode?: boolean;
      recommendation_id?: string;
      replay_run_id?: number;
      symbol?: string;
      side?: string;
      shares?: number;
      limit_price?: number;
      status?: string;
      estimated_entry_fee?: number | null;
      estimated_exit_fee?: number | null;
      estimated_total_fees?: number | null;
      projected_gross_pnl?: number | null;
      projected_net_pnl?: number | null;
      fee_model?: string | null;
    }>(
      "/api/user/orders",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    );
    if (!result.ok) {
      const message = result.status === 503
        ? "Configured provider unavailable. Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env."
        : (result.error ?? "Unable to stage order.");
      setError(message);
      setStatus("failed");
      setFeedback({ state: "error", message });
      setBusy(false);
      return;
    }

    const fallbackMode = result.data?.fallback_mode ?? false;
    const sourceName = result.data?.market_data_source ?? "provider";
    setDataSource(fallbackMode ? `fallback (${sourceName})` : sourceName);

    if (result.data?.order_id) {
      const hydrated: Order = {
        order_id: result.data.order_id,
        recommendation_id: result.data.recommendation_id ?? requestedRecommendation ?? guidedState.recommendationId ?? "",
        replay_run_id: result.data.replay_run_id ?? (guidedState.replayRunId ? Number(guidedState.replayRunId) : null),
        symbol: result.data.symbol ?? symbolHint ?? "—",
        side: result.data.side ?? "buy",
        shares: result.data.shares ?? 0,
        limit_price: result.data.limit_price ?? 0,
        status: result.data.status ?? "staged",
        created_at: new Date().toISOString(),
        market_data_source: sourceName,
        fallback_mode: fallbackMode,
        estimated_entry_fee: result.data.estimated_entry_fee ?? null,
        estimated_exit_fee: result.data.estimated_exit_fee ?? null,
        estimated_total_fees: result.data.estimated_total_fees ?? null,
        projected_gross_pnl: result.data.projected_gross_pnl ?? null,
        projected_net_pnl: result.data.projected_net_pnl ?? null,
        fee_model: result.data.fee_model ?? null,
        fills: [],
      };
      setOrders((prev) => [hydrated, ...prev.filter((item) => item.order_id !== hydrated.order_id)]);
      setSelectedOrderId(result.data.order_id);
      const query = buildGuidedQuery({
        guided: guidedState.guided,
        symbol: hydrated.symbol,
        strategy: guidedState.strategy,
        recommendationId: hydrated.recommendation_id,
        replayRunId: hydrated.replay_run_id != null ? String(hydrated.replay_run_id) : guidedState.replayRunId,
        source: sourceName,
        orderId: result.data.order_id,
      });
      router.replace(`/orders?${query}`);
    }

    setStatus("paper order staged");
    setFeedback({ state: "success", message: "Paper order staged." });
    await load();
    await Promise.all([loadPositions(), loadTrades()]);
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setBusy(false);
  }

  async function closePosition(orderId: string) {
    const price = parseFloat(closePriceInput);
    if (isNaN(price) || price <= 0) {
      setFeedback({ state: "error", message: "Enter a valid close price." });
      return;
    }
    setBusy(true);
    setFeedback({ state: "loading", message: "Closing position…" });
    const result = await fetchWorkflowApi<CloseResult>(
      `/api/user/orders/${orderId}/close`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ close_price: price }) },
    );
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Close position failed." });
      setBusy(false);
      return;
    }
    if (result.data) setCloseResults((prev) => ({ ...prev, [orderId]: result.data! }));
    setCloseInputVisible(false);
    setClosePriceInput("");
    setFeedback({ state: "success", message: "Position closed." });
    await load();
    setBusy(false);
  }

  async function loadPositions() {
    if (!authReady) return;
    const result = await fetchWorkflowApi<PaperPosition>("/api/user/paper-positions?status=open");
    if (result.ok) setPositions(result.items);
  }

  async function loadTrades() {
    if (!authReady) return;
    const result = await fetchWorkflowApi<PaperTrade>("/api/user/paper-trades?limit=50");
    if (result.ok) setTrades(result.items);
  }

  async function loadPortfolioSummary() {
    if (!authReady) return;
    const summary = await fetchWorkflowApi<PortfolioSummary>("/api/user/orders/portfolio-summary");
    if (summary.ok) setPortfolioSummary(summary.data ?? null);
  }

  function beginClosePosition(position: PaperPosition) {
    setClosingPositionId(position.id);
    setCloseMarkInput(position.avg_entry_price.toFixed(2));
    setCloseReasonInput(CLOSE_REASONS[0]);
  }

  function cancelClosePosition() {
    setClosingPositionId(null);
    setCloseMarkInput("");
    setCloseReasonInput(CLOSE_REASONS[0]);
  }

  async function confirmClosePosition(positionId: number) {
    const mark = parseFloat(closeMarkInput);
    if (!Number.isFinite(mark) || mark <= 0) {
      setFeedback({ state: "error", message: "Enter a valid mark price." });
      return;
    }
    setBusy(true);
    setFeedback({ state: "loading", message: "Closing paper position…" });
    const result = await fetchWorkflowApi<PaperTrade>(
      `/api/user/paper-positions/${positionId}/close`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mark_price: mark, reason: closeReasonInput }),
      },
    );
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Close paper position failed." });
      setBusy(false);
      return;
    }
    cancelClosePosition();
    setFeedback({
      state: "success",
      message: `Position closed — net P&L ${result.data ? formatSignedDollars(result.data.net_pnl) : "—"}`,
    });
    await Promise.all([loadPositions(), loadTrades(), loadPortfolioSummary()]);
    setBusy(false);
  }

  // Pass 4 — Cancel staged order
  async function confirmCancelOrder(orderId: string) {
    setBusy(true);
    setFeedback({ state: "loading", message: "Canceling order…" });
    const result = await fetchWorkflowApi<{ order_id: string; status: string; canceled_at: string | null }>(
      `/api/user/orders/${orderId}/cancel`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
    );
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Cancel order failed." });
      setBusy(false);
      return;
    }
    setCancelingOrderId(null);
    setFeedback({ state: "success", message: "Order canceled." });
    await Promise.all([load(), loadPositions()]);
    setBusy(false);
  }

  // Pass 4 — Reopen closed paper trade
  async function confirmReopenTrade(tradeId: number) {
    setBusy(true);
    setFeedback({ state: "loading", message: "Reopening position…" });
    const result = await fetchWorkflowApi<PaperPosition>(
      `/api/user/paper-trades/${tradeId}/reopen`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
    );
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Reopen position failed." });
      setBusy(false);
      return;
    }
    setReopeningTradeId(null);
    setFeedback({ state: "success", message: "Position reopened." });
    await Promise.all([loadPositions(), loadTrades(), loadPortfolioSummary()]);
    setBusy(false);
  }

  useEffect(() => {
    if (!authReady) return;
    void load();
    void loadPositions();
    void loadTrades();
  }, [searchKey, authReady]);

  // Refresh the reopen-window countdown every 30 seconds so closed-trade rows
  // lose their Reopen button automatically once 5 minutes have elapsed.
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  // Pass 4 — fetch display_id map for the workflow lineage card.
  useEffect(() => {
    if (!authReady) return;
    void fetchWorkflowApi<{ recommendation_id?: string; display_id?: string }>("/api/user/recommendations").then((r) => {
      if (!r.ok) return;
      const map: Record<string, string> = {};
      for (const item of r.items) {
        if (item.recommendation_id && item.display_id) map[item.recommendation_id] = item.display_id;
      }
      setDisplayIdMap(map);
    });
  }, [authReady]);

  useEffect(() => {
    if (!authReady || !guidedState.replayRunId) return;
    void (async () => {
      const result = await fetchWorkflowApi<{
        has_stageable_candidate: boolean;
        stageable_reason?: string | null;
        estimated_entry_fee?: number | null;
        estimated_exit_fee?: number | null;
        estimated_total_fees?: number | null;
        projected_gross_pnl?: number | null;
        projected_net_pnl?: number | null;
        fee_model?: string | null;
      }>(
        `/api/user/replay-runs/${guidedState.replayRunId}`,
      );
      if (result.ok) setReplayOutcome(result.data ?? null);
    })();
  }, [authReady, guidedState.replayRunId]);

  useEffect(() => {
    if (!selectedOrderId) return;
    setCloseInputVisible(false);
    setClosePriceInput("");
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selectedOrderId]);

  return <section className="op-stack">
    <PageHeader title="Paper Orders" subtitle="Step 4 action page: stage deterministic paper orders from replay lineage." actions={<StatusBadge tone="neutral">{busy ? "working…" : status}</StatusBadge>} />
    <WorkflowBanner
      current="Paper Order"
      state={{
        ...guidedState,
        symbol: selected?.symbol ?? guidedState.symbol,
        source: selected?.market_data_source ?? dataSource,
        recommendationId: selected?.recommendation_id ?? guidedState.recommendationId,
        replayRunId: selected?.replay_run_id != null ? String(selected.replay_run_id) : guidedState.replayRunId,
        orderId: selected?.order_id ?? guidedState.orderId,
      }}
      backHref="/replay-runs"
      backLabel="Back to Replay"
      nextDisabled={guidedState.guided && (!guidedState.recommendationId || !guidedState.replayRunId)}
      nextDisabledReason="Guided paper orders require both recommendation and replay lineage."
      compact={!guidedState.guided}
    />
    {guidedState.guided ? <Card title="Guided flow progress"><GuidedStepRail current="Paper Order" /></Card> : null}
    {portfolioSummary ? (
      <Card title="Paper portfolio">
        <div className="op-grid-4">
          <div><div style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>Open positions</div><strong>{portfolioSummary.open_positions}</strong></div>
          <div><div style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>Open notional</div><strong>${portfolioSummary.total_open_notional.toFixed(2)}</strong></div>
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>
              <MetricLabel label="Realized net P&L" term="net_pnl" />
            </div>
            <strong style={{ color: portfolioSummary.net_realized_pnl > 0 ? "#21c06e" : portfolioSummary.net_realized_pnl < 0 ? "#f44336" : "inherit" }}>
              {formatSignedDollars(portfolioSummary.net_realized_pnl)}
            </strong>
            <div style={{ marginTop: 4, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
              Gross {formatSignedDollars(portfolioSummary.gross_realized_pnl)} · Fees ${portfolioSummary.total_commission_paid.toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>Win rate</div>
            <strong>{portfolioSummary.win_rate != null ? `${(portfolioSummary.win_rate * 100).toFixed(1)}%` : "—"}</strong>
          </div>
        </div>
      </Card>
    ) : null}

    <Card title="What orders are for">
      Stage a paper order from replay-backed recommendation context before any live-route discussion.
      <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)" }}>Arriving here does not stage an order.</div>
    </Card>
    <Card title="Workflow lineage">
      <div>{(() => {
        const recId = selected?.recommendation_id ?? guidedState.recommendationId ?? null;
        const displayId = recId && displayIdMap[recId] ? displayIdMap[recId] : null;
        return formatLineageBreadcrumb(guidedState, {
          symbol: selected?.symbol ?? guidedState.symbol,
          strategy: guidedState.strategy,
          recommendationId: recId,
          recommendationDisplayId: displayId,
          replayRunId: selected?.replay_run_id ?? guidedState.replayRunId,
          orderId: selected?.order_id ?? guidedState.orderId,
        });
      })()}</div>
      {selected?.order_id ? (() => {
        const matchingOpen = positions.find((p) => p.order_id === selected.order_id);
        const matchingTrade = trades.find((t) => t.order_id === selected.order_id);
        if (!matchingOpen && !matchingTrade) return null;
        return (
          <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.88rem" }}>
            {matchingOpen ? <span>↳ open position #{matchingOpen.id}</span> : null}
            {matchingOpen && matchingTrade ? <span> · </span> : null}
            {matchingTrade ? (
              <span>
                ↳ closed trade #{matchingTrade.id} · net{" "}
                <span style={{ color: pnlColor(matchingTrade.net_pnl), fontWeight: 600 }}>
                  {formatSignedDollars(matchingTrade.net_pnl)}
                </span>{" "}
                after ${matchingTrade.commission_paid.toFixed(2)} fees
              </span>
            ) : null}
          </div>
        );
      })() : null}
    </Card>

    {guidedState.guided ? (
      <Card title="Paper order ticket">
        {!selected ? (
          <div className="op-card" style={{ padding: 12 }}>
            <h3 style={{ margin: "0 0 6px 0" }}>No paper order staged yet</h3>
            <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{guidedState.recommendationId ?? "—"}</span></div>
            <div><strong>replay run id:</strong> <span style={{ fontFamily: "monospace" }}>{guidedState.replayRunId ?? "—"}</span></div>
            <div><strong>symbol:</strong> {guidedState.symbol ?? "—"} · <strong>strategy:</strong> {guidedState.strategy ?? "—"}</div>
            {replayOutcome ? (
              <div style={{ marginTop: 8, padding: 10, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Estimated paper-only round trip (entry + exit)</div>
                <div><strong><MetricLabel label="Fees" term="equity_commission_per_trade" />:</strong> ${replayOutcome.estimated_total_fees?.toFixed(2) ?? "0.00"} ({replayOutcome.fee_model ?? "equity_per_trade"})</div>
                <div><strong>Entry fee:</strong> ${replayOutcome.estimated_entry_fee?.toFixed(2) ?? "0.00"} · <strong>Exit fee:</strong> ${replayOutcome.estimated_exit_fee?.toFixed(2) ?? "0.00"}</div>
                <div>
                  <strong><MetricLabel label="Projected net outcome" term="net_pnl" />:</strong>{" "}
                  {replayOutcome.projected_net_pnl != null
                    ? `${formatSignedDollars(replayOutcome.projected_net_pnl)}`
                    : "Unavailable for this candidate"}
                </div>
                {replayOutcome.projected_gross_pnl != null ? (
                  <div style={{ color: "var(--op-muted, #7a8999)" }}>
                    <MetricLabel label="Gross" term="gross_pnl" /> {formatSignedDollars(replayOutcome.projected_gross_pnl)} using existing recommendation levels.
                  </div>
                ) : (
                  <div style={{ color: "var(--op-muted, #7a8999)" }}>
                    Fees are estimated before staging. Net stays unavailable when a gross projection is not safe to derive.
                  </div>
                )}
              </div>
            ) : null}
            <button className="op-btn-primary-cta op-btn-pulse" style={{ marginTop: 8, width: "100%" }} onClick={() => void stagePaperOrder()} disabled={busy || unsupportedGuidedMode || replayOutcome?.has_stageable_candidate === false}>{busy ? "Staging..." : "Stage paper order now →"}</button>
            {replayOutcome?.has_stageable_candidate === false ? <div style={{ marginTop: 6, color: "var(--op-warn, #f2a03f)" }}>No paper order can be staged from this replay. {replayOutcome.stageable_reason ?? ""}</div> : null}
          </div>
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}><strong>symbol:</strong> {selected.symbol} · <strong>side:</strong> <StatusBadge tone={selected.side?.toLowerCase() === "buy" ? "good" : "warn"}>{selected.side}</StatusBadge> · <strong>shares:</strong> {selected.shares} · <strong>limit:</strong> {selected.limit_price}</div>
            <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{selected.recommendation_id}</span> · <strong>replay run id:</strong> <span style={{ fontFamily: "monospace" }}>{selected.replay_run_id ?? "—"}</span></div>
            <div><strong>source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)} · <strong>status:</strong> {selected.status}</div>
            <div style={{ color: "var(--op-muted, #7a8999)" }}>
              Estimated round-trip fees (entry + exit) ${selected.estimated_total_fees?.toFixed(2) ?? "0.00"} · paper-only preview
            </div>
          </>
        )}
      </Card>
    ) : null}

    <Card><div className="op-row"><button className={orderDoneForRec ? "op-btn op-btn-secondary" : "op-btn-primary-cta op-btn-pulse"} onClick={() => void stagePaperOrder()} disabled={busy || unsupportedGuidedMode || replayOutcome?.has_stageable_candidate === false}>{busy ? "Staging..." : orderDoneForRec ? "Stage another →" : "Stage paper order now →"}</button><button onClick={() => void load()} disabled={busy}>{busy ? "Refreshing..." : "Refresh order history"}</button></div><InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} /></Card>
    {error ? <ErrorState title="Orders unavailable" hint={error} /> : null}

    <Card title="Open paper positions">
      {positions.length === 0 ? (
        <EmptyState title="No open paper positions" hint="Stage a paper order from a replay-validated recommendation to open a position." />
      ) : (
        <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
          <table className="op-table">
            <thead>
              <tr>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>side</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>remaining qty</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>avg entry</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>opened</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>recommendation</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}></th>
              </tr>
            </thead>
            <tbody>
              {positions.flatMap((p) => {
                const rows: React.ReactNode[] = [
                  <tr key={p.id}>
                    <td>{p.symbol}</td>
                    <td><span className={`op-side-badge is-${p.side.toLowerCase()}`}>{p.side}</span></td>
                    <td>{p.remaining_qty}</td>
                    <td>{p.avg_entry_price.toFixed(2)}</td>
                    <td>{formatRelativeTime(p.opened_at)}</td>
                    <td>
                      {p.recommendation_id ? (
                        <Link
                          href={`/recommendations?${buildGuidedQuery({ ...guidedState, recommendationId: p.recommendation_id, symbol: p.symbol })}`}
                          style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
                        >
                          {displayIdMap[p.recommendation_id] ?? p.recommendation_id}
                        </Link>
                      ) : "—"}
                    </td>
                    <td>
                      {closingPositionId === p.id ? null : (
                        <button className="op-btn op-btn-destructive" onClick={() => beginClosePosition(p)} disabled={busy}>Close position</button>
                      )}
                    </td>
                  </tr>,
                ];
                if (closingPositionId === p.id) {
                  const closePreview = (() => {
                    const mark = parseFiniteNumber(closeMarkInput);
                    if (mark == null) return null;
                    return estimateClosePnl({
                      entryPrice: p.avg_entry_price,
                      exitPrice: mark,
                      quantity: p.remaining_qty,
                      side: p.side,
                      estimatedCloseFee: p.estimated_close_fee ?? 0,
                    });
                  })();
                  rows.push(
                    <tr key={`${p.id}-ticket`}>
                      <td colSpan={7} style={{ background: "var(--card-bg-alt, #0e1822)", padding: 12 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: "0.85rem", color: "var(--op-muted, #7a8999)" }}>Mark price</span>
                            <input
                              type="number"
                              step="0.01"
                              required
                              value={closeMarkInput}
                              onChange={(e) => setCloseMarkInput(e.target.value)}
                              style={{ width: 120 }}
                            />
                          </label>
                          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: "0.85rem", color: "var(--op-muted, #7a8999)" }}>Reason</span>
                            <select value={closeReasonInput} onChange={(e) => setCloseReasonInput(e.target.value)}>
                              {CLOSE_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                            </select>
                          </label>
                          <button className="op-btn op-btn-destructive" onClick={() => void confirmClosePosition(p.id)} disabled={busy}>{busy ? "Closing…" : "Confirm close"}</button>
                          <button onClick={cancelClosePosition} disabled={busy}>Cancel</button>
                        </div>
                        <div style={{ marginTop: 8, fontSize: "0.85rem", color: "var(--op-muted, #7a8999)" }}>
                          Estimated close-only fee ${p.estimated_close_fee?.toFixed(2) ?? "0.00"} · paper-only preview
                        </div>
                        {closePreview ? (
                          <div style={{ marginTop: 4, fontSize: "0.9rem" }}>
                            Gross <span style={{ color: pnlColor(closePreview.gross), fontWeight: 600 }}>{formatSignedDollars(closePreview.gross)}</span>
                            {" "}· Net after fees <span style={{ color: pnlColor(closePreview.net), fontWeight: 600 }}>{formatSignedDollars(closePreview.net)}</span>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  );
                }
                return rows;
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>

    <PaperOptionsPositionsSection enabled={authReady} />

    <div className="op-grid-2">
      <Card title={guidedState.guided ? "Order history (secondary)" : "Order history"}>
        {guidedState.guided ? <div style={{ marginBottom: 6, color: "var(--op-muted, #7a8999)" }}>Secondary panel: full order history</div> : null}
        <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
        <table className="op-table" style={{ marginTop: guidedState.guided ? 8 : 0 }}>
          <thead><tr><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>created_at</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>side</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>shares</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>limit/fill</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>broker status</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>fill count</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}></th></tr></thead>
          <tbody>
            {orders.length === 0 && !busy ? <tr><td colSpan={8} style={{ color: "#9fb0c3", textAlign: "center", padding: "16px 8px" }}>No paper orders yet. Click "Stage paper order now" above to create your first order.</td></tr> : null}
            {orders.flatMap((o) => {
              const cancelable = o.status === "staged" && (o.fills?.length ?? 0) === 0;
              const rowEls: React.ReactNode[] = [
                <tr key={o.order_id} onClick={() => setSelectedOrderId(o.order_id)} className={`is-selectable ${selectedOrderId === o.order_id ? "is-active" : ""}`}>
                  <td>{o.created_at}</td>
                  <td>{o.symbol}</td>
                  <td><span className={`op-side-badge is-${o.side.toLowerCase()}`}>{o.side}</span></td>
                  <td>{o.shares}</td>
                  <td>{o.limit_price} / {o.fills[0]?.fill_price ?? "-"}</td>
                  <td><StatusBadge tone={o.status.includes("fill") ? "good" : "warn"}>{o.status}</StatusBadge></td>
                  <td>{o.fills.length}</td>
                  <td>
                    {cancelable && cancelingOrderId !== o.order_id ? (
                      <button
                        className="op-btn op-btn-destructive"
                        onClick={(e) => { e.stopPropagation(); setCancelingOrderId(o.order_id); }}
                        disabled={busy}
                      >Cancel order</button>
                    ) : null}
                  </td>
                </tr>,
              ];
              if (cancelable && cancelingOrderId === o.order_id) {
                rowEls.push(
                  <tr key={`${o.order_id}-confirm`}>
                    <td colSpan={8} style={{ background: "var(--card-bg-alt, #0e1822)", padding: 12 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                        <span style={{ fontSize: "0.9rem" }}>Are you sure? This cannot be undone.</span>
                        <button
                          className="op-btn op-btn-destructive"
                          onClick={(e) => { e.stopPropagation(); void confirmCancelOrder(o.order_id); }}
                          disabled={busy}
                        >{busy ? "Canceling…" : "Yes, cancel"}</button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setCancelingOrderId(null); }}
                          disabled={busy}
                        >No</button>
                      </div>
                    </td>
                  </tr>
                );
              }
              return rowEls;
            })}
          </tbody>
        </table>
        </div>
      </Card>
      <Card title="Selected order detail">
        {guidedState.guided ? <div className="op-row" style={{ marginBottom: 8 }}><button onClick={() => setShowOperatorDetail((prev) => !prev)}>{showOperatorDetail ? "Hide operator detail" : "Show operator detail"}</button></div> : null}
        <div ref={detailRef}>
          {!selected ? <EmptyState title="Select an order" hint="Click a blotter row to inspect paper-broker fill details." /> : <div style={{ display: "grid", gap: 6 }}>
            <div><strong>Order id:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selected.order_id}</span></div>
            <div><strong>Recommendation:</strong> <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{selected.recommendation_id}</span></div>
            <div><strong>Replay run:</strong> {selected.replay_run_id ?? "—"}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}><strong>Symbol/side:</strong> {selected.symbol} <StatusBadge tone={selected.side?.toLowerCase() === "buy" ? "good" : "warn"}>{selected.side}</StatusBadge></div>
            <div><strong>Shares:</strong> {selected.shares}</div>
            <div><strong>Limit:</strong> {selected.limit_price}</div>
            <div><strong>Status:</strong> {selected.status}</div>
            <div><strong>Workflow source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)}</div>
            <div style={{ marginTop: 4, padding: 10, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
              <div style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Estimated paper-only lifecycle (entry + exit)</div>
              <div><strong>Entry fee:</strong> ${selected.estimated_entry_fee?.toFixed(2) ?? "0.00"} · <strong>Exit fee:</strong> ${selected.estimated_exit_fee?.toFixed(2) ?? "0.00"}</div>
              <div><strong><MetricLabel label="Total fees" term="equity_commission_per_trade" />:</strong> ${selected.estimated_total_fees?.toFixed(2) ?? "0.00"} ({selected.fee_model ?? "equity_per_trade"})</div>
              <div>
                <strong><MetricLabel label="Projected net outcome" term="net_pnl" />:</strong>{" "}
                {selected.projected_net_pnl != null ? formatSignedDollars(selected.projected_net_pnl) : "Unavailable"}
              </div>
              {selected.projected_gross_pnl != null ? (
                <div style={{ color: "var(--op-muted, #7a8999)" }}>
                  <MetricLabel label="Gross" term="gross_pnl" /> {formatSignedDollars(selected.projected_gross_pnl)} using existing recommendation levels.
                </div>
              ) : null}
            </div>
            {(!guidedState.guided || showOperatorDetail) ? <><div><strong>Created at:</strong> {selected.created_at}</div><div><strong>Fills:</strong></div>{selected.fills.map((fill, idx) => <div key={idx}>#{idx + 1} {fill.filled_shares} @ {fill.fill_price} ({fill.timestamp})</div>)}</> : null}
            {selected.status === "closed" ? (
              <div style={{ marginTop: 6, fontWeight: 600, color: closeResults[selected.order_id]?.net_pnl != null && closeResults[selected.order_id].net_pnl >= 0 ? "#21c06e" : "#f44336" }}>
                {closeResults[selected.order_id]
                  ? `Closed — Net P&L: ${formatSignedDollars(closeResults[selected.order_id].net_pnl)} (gross ${formatSignedDollars(closeResults[selected.order_id].gross_pnl)}, fees $${closeResults[selected.order_id].commission_paid.toFixed(2)})`
                  : "Position closed"}
              </div>
            ) : (
              <div style={{ marginTop: 6 }}>
                <div style={{ marginBottom: 6, color: "var(--op-muted, #7a8999)" }}>
                  Estimated close-only fee ${selectedOpenPosition?.estimated_close_fee?.toFixed(2) ?? selected.estimated_exit_fee?.toFixed(2) ?? "0.00"} · paper-only preview
                </div>
                {!closeInputVisible ? (
                  <button className="op-btn op-btn-destructive" onClick={() => { setCloseInputVisible(true); setClosePriceInput(String(selected.limit_price)); }} disabled={busy}>Close position</button>
                ) : (
                  <>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <input type="number" step="0.01" value={closePriceInput} onChange={(e) => setClosePriceInput(e.target.value)} style={{ width: 120 }} placeholder="Close price" />
                      <button className="op-btn op-btn-destructive" onClick={() => void closePosition(selected.order_id)} disabled={busy}>{busy ? "Closing…" : "Confirm close"}</button>
                      <button onClick={() => { setCloseInputVisible(false); setClosePriceInput(""); }} disabled={busy}>Cancel</button>
                    </div>
                    {selectedClosePreview ? (
                      <div style={{ marginTop: 8 }}>
                        <MetricLabel label="Gross" term="gross_pnl" /> <span style={{ color: pnlColor(selectedClosePreview.gross), fontWeight: 600 }}>{formatSignedDollars(selectedClosePreview.gross)}</span>
                        {" "}· Net after fees <span style={{ color: pnlColor(selectedClosePreview.net), fontWeight: 600 }}>{formatSignedDollars(selectedClosePreview.net)}</span>
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            )}
          </div>}
        </div>
      </Card>
    </div>

    <Card title="Closed trades (last 50)">
      {trades.length === 0 ? (
        <EmptyState title="No closed trades yet." hint="Close an open paper position to record a realized trade." />
      ) : (
        <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
          <table className="op-table">
            <thead>
              <tr>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>side</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>qty</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>entry → exit</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}><MetricLabel label="gross P&L" term="gross_pnl" /></th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}><MetricLabel label="fees" term="equity_commission_per_trade" /></th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}><MetricLabel label="net P&L" term="net_pnl" /></th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>hold</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>reason</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>closed</th>
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}></th>
              </tr>
            </thead>
            <tbody>
              {trades.flatMap((t) => {
                const reopenable = canReopenTrade(t.closed_at, nowMs);
                const remaining = reopenSecondsRemaining(t.closed_at, nowMs);
                const tradeRows: React.ReactNode[] = [
                  <tr key={t.id}>
                    <td>{t.symbol}</td>
                    <td><span className={`op-side-badge is-${t.side.toLowerCase()}`}>{t.side}</span></td>
                    <td>{t.qty}</td>
                    <td>{t.entry_price.toFixed(2)} → {t.exit_price != null ? t.exit_price.toFixed(2) : "—"}</td>
                    <td style={{ color: pnlColor(t.gross_pnl), fontWeight: 600 }}>
                      {formatSignedDollars(t.gross_pnl)}
                    </td>
                    <td>${t.commission_paid.toFixed(2)}</td>
                    <td style={{ color: pnlColor(t.net_pnl), fontWeight: 600 }}>
                      {formatSignedDollars(t.net_pnl)}
                    </td>
                    <td>{formatHoldDuration(t.hold_seconds)}</td>
                    <td>{t.close_reason ?? "—"}</td>
                    <td>{formatRelativeTime(t.closed_at)}</td>
                    <td>
                      {reopenable && reopeningTradeId !== t.id ? (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          <button
                            className="op-btn op-btn-secondary"
                            onClick={() => setReopeningTradeId(t.id)}
                            disabled={busy}
                          >Reopen position</button>
                          <span style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>(undo within {remaining}s)</span>
                        </span>
                      ) : null}
                    </td>
                  </tr>,
                ];
                if (reopenable && reopeningTradeId === t.id) {
                  tradeRows.push(
                    <tr key={`${t.id}-reopen-confirm`}>
                      <td colSpan={11} style={{ background: "var(--card-bg-alt, #0e1822)", padding: 12 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                          <span style={{ fontSize: "0.9rem" }}>Are you sure? This cannot be undone.</span>
                          <button
                            className="op-btn op-btn-secondary"
                            onClick={() => void confirmReopenTrade(t.id)}
                            disabled={busy}
                          >{busy ? "Reopening…" : "Yes, reopen"}</button>
                          <button onClick={() => setReopeningTradeId(null)} disabled={busy}>No</button>
                        </div>
                      </td>
                    </tr>
                  );
                }
                return tradeRows;
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  </section>;
}
