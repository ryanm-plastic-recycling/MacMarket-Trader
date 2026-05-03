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
  formatMarkAsOfTime,
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
  recommended_shares?: number | null;
  final_order_shares?: number | null;
  operator_override_shares?: number | null;
  notional_cap_shares?: number | null;
  max_paper_order_notional?: number | null;
  estimated_notional?: number | null;
  risk_at_stop?: number | null;
  sizing_mode?: string | null;
  notional_cap_reduced?: boolean | null;
  risk_calendar?: RiskCalendarPayload | null;
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

type PaperPositionReview = {
  position_id: number;
  symbol: string;
  side: string;
  quantity: number | null;
  average_entry_price: number | null;
  current_mark_price: number | null;
  market_data_source: string | null;
  market_data_fallback_mode: boolean;
  mark_as_of: string | number | null;
  market_session_policy: string | null;
  unrealized_pnl: number | null;
  unrealized_return_pct: number | null;
  estimated_current_notional: number | null;
  entry_notional: number | null;
  stop_price: number | null;
  target_1: number | null;
  target_2: number | null;
  distance_to_stop_pct: number | null;
  distance_to_target_1_pct: number | null;
  distance_to_target_2_pct: number | null;
  days_held: number | null;
  holding_period_status: string;
  risk_calendar?: RiskCalendarPayload | null;
  current_recommendation_status: string;
  current_rank: number | null;
  already_open: boolean;
  action_classification: string;
  action_summary: string;
  warnings: string[];
  missing_data: string[];
};

type OptionLegReview = {
  leg_id: number;
  option_symbol: string | null;
  underlying_symbol: string;
  expiration: string | null;
  option_type: "call" | "put" | string;
  strike: number;
  side: "long" | "short" | string;
  contracts: number;
  opening_premium: number | null;
  current_mark_premium: number | null;
  mark_method: string;
  implied_volatility: number | null;
  open_interest: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  underlying_price: number | null;
  estimated_leg_unrealized_pnl: number | null;
  market_data_source: string | null;
  market_data_fallback_mode: boolean;
  mark_as_of: string | number | null;
  stale: boolean;
  missing_data: string[];
};

type OptionStructureReview = {
  structure_id: number;
  underlying_symbol: string;
  strategy_type: string;
  side: string | null;
  opened_at: string;
  expiration_date: string | null;
  days_to_expiration: number | null;
  contracts: number | null;
  quantity: number | null;
  multiplier_assumption: number | null;
  opening_debit_credit: number | null;
  opening_debit_credit_type: "debit" | "credit" | "unknown" | string;
  opening_commissions: number | null;
  current_mark_debit_credit: number | null;
  current_mark_debit_credit_type: "debit" | "credit" | "unknown" | string;
  estimated_unrealized_gross_pnl: number | null;
  estimated_closing_commissions: number | null;
  estimated_total_commissions: number | null;
  estimated_unrealized_pnl: number | null;
  estimated_unrealized_return_pct: number | null;
  max_profit: number | null;
  max_loss: number | null;
  breakevens: number[];
  payoff_summary: string | null;
  risk_calendar?: RiskCalendarPayload | null;
  expiration_status: string;
  action_classification: string;
  action_summary: string;
  warnings: string[];
  missing_data: string[];
  legs: OptionLegReview[];
};

type PaperTrade = {
  id: number;
  symbol: string;
  side: string;
  qty: number;
  entry_price: number;
  exit_price: number | null;
  entry_notional?: number | null;
  exit_notional?: number | null;
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

type UserPaperSettings = {
  paper_max_order_notional: number | null;
  paper_max_order_notional_default: number | null;
};

type RecommendationRow = {
  recommendation_id: string;
  payload?: {
    sizing?: { shares?: number; risk_dollars?: number; stop_distance?: number };
    entry?: { zone_low?: number; zone_high?: number };
    invalidation?: { price?: number };
    risk_calendar?: RiskCalendarPayload | null;
  };
  already_open?: boolean;
  open_position_id?: number | null;
  open_position_quantity?: number | null;
  open_position_average_entry?: number | null;
  active_review_action_classification?: string | null;
  active_review_summary?: string | null;
  open_position_review_path?: string | null;
};
type RiskCalendarPayload = {
  decision?: {
    decision_state?: string;
    risk_level?: string;
    recommended_action?: string;
    warning_summary?: string;
    block_reason?: string | null;
    allow_new_entries?: boolean;
    requires_confirmation?: boolean;
    missing_evidence?: string[];
    active_events?: Array<{ title?: string; event_type?: string; impact?: string }>;
  };
};

type OrderSizingPreview = {
  recommendedShares: number;
  finalOrderShares: number;
  enteredShares: number;
  limitPrice: number;
  estimatedNotional: number;
  riskAtStop: number;
  maxPaperOrderNotional: number;
  notionalCapShares: number;
  capReduced: boolean;
};

type RecommendationOpenContext = Pick<
  RecommendationRow,
  | "already_open"
  | "open_position_id"
  | "open_position_quantity"
  | "open_position_average_entry"
  | "active_review_action_classification"
  | "active_review_summary"
  | "open_position_review_path"
>;

const CLOSE_REASONS = ["Target hit", "Stop hit", "Manual exit", "Time exit", "Other"] as const;

function formatSignedDollars(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatDollars(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatMaybeDollars(value: number | null | undefined): string {
  return Number.isFinite(Number(value)) ? formatDollars(Number(value)) : "Unavailable";
}

function formatMaybePercent(value: number | null | undefined): string {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : "Unavailable";
}

function riskTone(risk?: RiskCalendarPayload | null): "good" | "warn" | "bad" | "neutral" {
  const decision = risk?.decision;
  if (!decision) return "neutral";
  if (decision.decision_state === "normal") return "good";
  return decision.allow_new_entries ? "warn" : "bad";
}

function actionTone(action: string): "good" | "warn" | "bad" | "neutral" {
  if (["hold_valid", "target_reached_hold", "scale_in_candidate"].includes(action)) return "good";
  if (["stop_triggered", "time_stop_exit", "invalidated", "review_unavailable"].includes(action)) return "bad";
  if (["target_reached_take_profit", "time_stop_warning"].includes(action)) return "warn";
  return "neutral";
}

function optionActionTone(action: string): "good" | "warn" | "bad" | "neutral" {
  if (["hold_valid", "profitable_hold"].includes(action)) return "good";
  if (["review_unavailable", "expiration_due", "max_loss_near"].includes(action)) return "bad";
  if (["mark_unavailable", "expiration_warning", "max_profit_near", "close_candidate", "adjustment_review", "losing_hold"].includes(action)) return "warn";
  return "neutral";
}

function formatOptionStructureToken(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim();
  if (!normalized) return "Unknown";
  return normalized
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function formatOpeningDebitCredit(review: OptionStructureReview): string {
  if (review.opening_debit_credit == null) return "Unavailable";
  const label = review.opening_debit_credit_type === "credit" ? "Credit" : review.opening_debit_credit_type === "debit" ? "Debit" : "Open";
  return `${label} ${formatMaybeDollars(review.opening_debit_credit)}`;
}

function formatBreakevenList(values: number[] | null | undefined): string {
  const safeValues = (values ?? []).filter((value) => Number.isFinite(Number(value)));
  return safeValues.length ? safeValues.map((value) => formatMaybeDollars(value)).join(" / ") : "Unavailable";
}

function formatDte(value: number | null | undefined): string {
  if (!Number.isFinite(Number(value))) return "DTE unavailable";
  const days = Number(value);
  if (days < 0) return `${Math.abs(days)}d past expiration`;
  if (days === 0) return "expires today";
  return `${days}d`;
}

function formatMaybeDecimal(value: number | null | undefined, digits = 2): string {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "Unavailable";
}

function formatMaybeIv(value: number | null | undefined): string {
  if (!Number.isFinite(Number(value))) return "IV unavailable";
  return `${(Number(value) * 100).toFixed(1)}% IV`;
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

function buildSizingPreview(
  payload: RecommendationRow["payload"] | null,
  maxPaperOrderNotional: number | null,
  orderSharesInput: string,
): OrderSizingPreview | null {
  const recommendedShares = Number(payload?.sizing?.shares);
  const zoneLow = Number(payload?.entry?.zone_low);
  const zoneHigh = Number(payload?.entry?.zone_high);
  const stop = Number(payload?.invalidation?.price);
  const cap = Number(maxPaperOrderNotional);
  if (![recommendedShares, zoneLow, zoneHigh, stop, cap].every(Number.isFinite)) return null;
  if (recommendedShares <= 0 || cap <= 0) return null;
  const limitPrice = (zoneLow + zoneHigh) / 2;
  if (!Number.isFinite(limitPrice) || limitPrice <= 0) return null;
  const notionalCapShares = Math.floor(cap / limitPrice);
  const defaultShares = Math.max(0, Math.min(recommendedShares, notionalCapShares));
  const parsedInput = Number.parseInt(orderSharesInput, 10);
  const enteredShares = Number.isFinite(parsedInput) && parsedInput > 0 ? parsedInput : defaultShares;
  const stopDistance = Math.abs(limitPrice - stop);
  return {
    recommendedShares,
    finalOrderShares: Math.min(enteredShares, defaultShares),
    enteredShares,
    limitPrice,
    estimatedNotional: enteredShares * limitPrice,
    riskAtStop: enteredShares * stopDistance,
    maxPaperOrderNotional: cap,
    notionalCapShares,
    capReduced: notionalCapShares < recommendedShares,
  };
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
  const [positionReviews, setPositionReviews] = useState<PaperPositionReview[]>([]);
  const [optionStructureReviews, setOptionStructureReviews] = useState<OptionStructureReview[]>([]);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [paperSettings, setPaperSettings] = useState<UserPaperSettings | null>(null);
  const [recommendationPayloadMap, setRecommendationPayloadMap] = useState<Record<string, RecommendationRow["payload"]>>({});
  const [recommendationOpenContextMap, setRecommendationOpenContextMap] = useState<Record<string, RecommendationOpenContext>>({});
  const [orderSharesInput, setOrderSharesInput] = useState("");
  const [riskCalendarConfirmed, setRiskCalendarConfirmed] = useState(false);
  const [riskCalendarOverrideReason, setRiskCalendarOverrideReason] = useState("");
  const [showSandboxTools, setShowSandboxTools] = useState(false);
  const [resetConfirmInput, setResetConfirmInput] = useState("");
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
  const e2eBypass = isE2EAuthBypassEnabled();
  const authReady = e2eBypass || (isLoaded && isSignedIn);
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
  const activeRecommendationId = selected?.recommendation_id ?? guidedState.recommendationId ?? new URLSearchParams(searchKey).get("recommendation");
  const effectivePaperMaxNotional = paperSettings?.paper_max_order_notional ?? paperSettings?.paper_max_order_notional_default ?? null;
  const orderSizingPreview = useMemo(
    () => buildSizingPreview(
      activeRecommendationId ? recommendationPayloadMap[activeRecommendationId] ?? null : null,
      effectivePaperMaxNotional,
      orderSharesInput,
    ),
    [activeRecommendationId, effectivePaperMaxNotional, orderSharesInput, recommendationPayloadMap],
  );
  const activeRiskCalendar = activeRecommendationId
    ? recommendationPayloadMap[activeRecommendationId]?.risk_calendar ?? null
    : selected?.risk_calendar ?? null;
  const activeOpenContext = activeRecommendationId
    ? recommendationOpenContextMap[activeRecommendationId] ?? null
    : null;
  const activeExposurePreview = activeOpenContext?.already_open && orderSizingPreview
      ? {
        existingQuantity: activeOpenContext.open_position_quantity ?? null,
        newQuantity: orderSizingPreview.finalOrderShares,
        newNotional: orderSizingPreview.finalOrderShares * orderSizingPreview.limitPrice,
        combinedQuantity:
          activeOpenContext.open_position_quantity != null
            ? activeOpenContext.open_position_quantity + orderSizingPreview.finalOrderShares
            : null,
        combinedEstimatedNotional:
          activeOpenContext.open_position_quantity != null && activeOpenContext.open_position_average_entry != null
            ? activeOpenContext.open_position_quantity * activeOpenContext.open_position_average_entry
              + orderSizingPreview.finalOrderShares * orderSizingPreview.limitPrice
            : null,
      }
    : null;

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
    if (orderSharesInput.trim()) {
      const overrideShares = Number.parseInt(orderSharesInput, 10);
      if (!Number.isFinite(overrideShares) || overrideShares <= 0 || String(overrideShares) !== orderSharesInput.trim()) {
        setFeedback({ state: "error", message: "Order shares must be a positive whole number." });
        setBusy(false);
        return;
      }
      body.override_shares = overrideShares;
    }

    body.market_mode = guidedState.marketMode ?? "equities";
    if (guidedState.guided) {
      body.guided = true;
      if (guidedState.replayRunId) body.replay_run_id = Number(guidedState.replayRunId);
    }
    if (riskCalendarConfirmed) body.risk_calendar_confirmed = true;
    if (riskCalendarOverrideReason.trim()) body.risk_calendar_override_reason = riskCalendarOverrideReason.trim();

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
      recommended_shares?: number | null;
      final_order_shares?: number | null;
      operator_override_shares?: number | null;
      notional_cap_shares?: number | null;
      max_paper_order_notional?: number | null;
      estimated_notional?: number | null;
      risk_at_stop?: number | null;
      sizing_mode?: string | null;
      notional_cap_reduced?: boolean | null;
      risk_calendar?: RiskCalendarPayload | null;
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
        recommended_shares: result.data.recommended_shares ?? null,
        final_order_shares: result.data.final_order_shares ?? result.data.shares ?? null,
        operator_override_shares: result.data.operator_override_shares ?? null,
        notional_cap_shares: result.data.notional_cap_shares ?? null,
        max_paper_order_notional: result.data.max_paper_order_notional ?? null,
        estimated_notional: result.data.estimated_notional ?? null,
        risk_at_stop: result.data.risk_at_stop ?? null,
        sizing_mode: result.data.sizing_mode ?? null,
        notional_cap_reduced: result.data.notional_cap_reduced ?? null,
        risk_calendar: result.data.risk_calendar ?? null,
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
    setRiskCalendarConfirmed(false);
    setRiskCalendarOverrideReason("");
    await load();
    await Promise.all([loadPositions(), loadPositionReviews(), loadOptionStructureReviews(), loadTrades()]);
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

  async function loadPositionReviews() {
    if (!authReady) return;
    const result = await fetchWorkflowApi<PaperPositionReview>("/api/user/paper-positions/review");
    if (result.ok) setPositionReviews(result.items);
  }

  async function loadOptionStructureReviews() {
    if (!authReady) return;
    const result = await fetchWorkflowApi<OptionStructureReview>("/api/user/options/paper-structures/review");
    if (result.ok) setOptionStructureReviews(result.items);
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

  async function loadPaperSettings() {
    if (!authReady) return;
    const result = await fetchWorkflowApi<UserPaperSettings>("/api/user/settings");
    if (result.ok) setPaperSettings(result.data ?? null);
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
    await Promise.all([loadPositions(), loadPositionReviews(), loadOptionStructureReviews(), loadTrades(), loadPortfolioSummary()]);
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
    await Promise.all([load(), loadPositions(), loadPositionReviews(), loadOptionStructureReviews()]);
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
    await Promise.all([loadPositions(), loadPositionReviews(), loadOptionStructureReviews(), loadTrades(), loadPortfolioSummary()]);
    setBusy(false);
  }

  async function resetPaperSandbox() {
    if (resetConfirmInput !== "RESET") {
      setFeedback({ state: "error", message: "Type RESET to confirm paper sandbox reset." });
      return;
    }
    setBusy(true);
    setFeedback({ state: "loading", message: "Resetting paper sandbox..." });
    const result = await fetchWorkflowApi<{ status: string; counts: Record<string, number> }>(
      "/api/user/paper/reset",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation: resetConfirmInput }),
      },
    );
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Paper sandbox reset failed." });
      setBusy(false);
      return;
    }
    setOrders([]);
    setPositions([]);
    setPositionReviews([]);
    setTrades([]);
    setSelectedOrderId(null);
    setResetConfirmInput("");
    setFeedback({ state: "success", message: "Paper sandbox reset complete." });
    await Promise.all([load(), loadPositions(), loadPositionReviews(), loadOptionStructureReviews(), loadTrades(), loadPortfolioSummary()]);
    setBusy(false);
  }

  useEffect(() => {
    if (!authReady) return;
    void load();
    void loadPositions();
    void loadPositionReviews();
    void loadOptionStructureReviews();
    void loadTrades();
    void loadPaperSettings();
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
      const payloads: Record<string, RecommendationRow["payload"]> = {};
      const openContexts: Record<string, RecommendationOpenContext> = {};
      for (const item of r.items as RecommendationRow[]) {
        if (item.recommendation_id) payloads[item.recommendation_id] = item.payload;
        if (item.recommendation_id) {
          openContexts[item.recommendation_id] = {
            already_open: item.already_open,
            open_position_id: item.open_position_id,
            open_position_quantity: item.open_position_quantity,
            open_position_average_entry: item.open_position_average_entry,
            active_review_action_classification: item.active_review_action_classification,
            active_review_summary: item.active_review_summary,
            open_position_review_path: item.open_position_review_path,
          };
        }
      }
      setRecommendationPayloadMap(payloads);
      setRecommendationOpenContextMap(openContexts);
    });
  }, [authReady]);

  useEffect(() => {
    if (selected || !orderSizingPreview || orderSharesInput.trim()) return;
    setOrderSharesInput(String(orderSizingPreview.finalOrderShares));
  }, [orderSharesInput, orderSizingPreview, selected]);

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
    if (!authReady || !guidedState.replayRunId) return;
    void (async () => {
      const result = await fetchWorkflowApi<{ has_stageable_candidate: boolean; stageable_reason?: string | null }>(
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

    <Card title="Paper sandbox tools">
      <button className="op-btn op-btn-secondary" onClick={() => setShowSandboxTools((prev) => !prev)}>
        {showSandboxTools ? "Hide testing tools" : "Show testing tools"}
      </button>
      {showSandboxTools ? (
        <div style={{ marginTop: 10, display: "grid", gap: 10 }}>
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.88rem", lineHeight: 1.5 }}>
            Reset deletes only your current equity paper orders, fills, positions, and closed paper trades. Recommendations, replay runs, settings, watchlists, provider config, and options-paper rows stay intact.
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span>Type RESET</span>
            <input
              value={resetConfirmInput}
              onChange={(e) => setResetConfirmInput(e.target.value)}
              placeholder="RESET"
              style={{ width: 140 }}
            />
          </label>
          <button
            className="op-btn op-btn-destructive"
            onClick={() => void resetPaperSandbox()}
            disabled={busy || resetConfirmInput !== "RESET"}
          >
            Reset my paper portfolio
          </button>
        </div>
      ) : null}
    </Card>

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
            {orderSizingPreview ? (
              <div style={{ marginTop: 8, padding: 10, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Paper-only sizing</div>
                <div className="op-grid-4" style={{ marginTop: 6 }}>
                  <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Recommended shares</div><strong>{orderSizingPreview.recommendedShares}</strong></div>
                  <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Estimated notional</div><strong>{formatDollars(orderSizingPreview.estimatedNotional)}</strong></div>
                  <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Risk at stop</div><strong>{formatDollars(orderSizingPreview.riskAtStop)}</strong></div>
                  <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Max paper order value</div><strong>{formatDollars(orderSizingPreview.maxPaperOrderNotional)}</strong></div>
                </div>
                <label style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span>Order shares</span>
                  <input
                    type="number"
                    min={1}
                    max={Math.min(orderSizingPreview.recommendedShares, orderSizingPreview.notionalCapShares)}
                    step={1}
                    value={orderSharesInput}
                    onChange={(e) => setOrderSharesInput(e.target.value)}
                    style={{ width: 110 }}
                  />
                  <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                    cap allows up to {orderSizingPreview.notionalCapShares} shares at {formatDollars(orderSizingPreview.limitPrice)}
                  </span>
                </label>
                {orderSizingPreview.capReduced ? (
                  <div style={{ marginTop: 6, color: "var(--op-warn, #f2a03f)", fontSize: "0.86rem" }}>
                    Max paper order value reduced the default paper order from {orderSizingPreview.recommendedShares} to {Math.min(orderSizingPreview.recommendedShares, orderSizingPreview.notionalCapShares)} shares.
                  </div>
                ) : null}
              </div>
            ) : null}
            {activeOpenContext?.already_open ? (
              <div style={{ marginTop: 8, padding: 10, border: "1px solid var(--op-warn, #f2a03f)", borderRadius: 8, color: "var(--op-warn, #f2a03f)" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <StatusBadge tone="warn">Already open</StatusBadge>
                  <Link href={activeOpenContext.open_position_review_path || "/orders#active-position-review"}>Review existing paper position</Link>
                </div>
                <div style={{ marginTop: 6 }}>
                  Additional paper order would increase exposure.
                </div>
                {activeExposurePreview ? (
                  <div className="op-grid-4" style={{ marginTop: 6 }}>
                    <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Existing quantity</div><strong>{activeExposurePreview.existingQuantity ?? "Unavailable"}</strong></div>
                    <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>New order quantity</div><strong>{activeExposurePreview.newQuantity}</strong></div>
                    <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Combined quantity</div><strong>{activeExposurePreview.combinedQuantity ?? "Unavailable"}</strong></div>
                    <div><div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Combined estimated notional</div><strong>{activeExposurePreview.combinedEstimatedNotional != null ? formatDollars(activeExposurePreview.combinedEstimatedNotional) : "Unavailable"}</strong></div>
                  </div>
                ) : null}
                {activeOpenContext.active_review_summary ? (
                  <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)" }}>{activeOpenContext.active_review_summary}</div>
                ) : null}
              </div>
            ) : null}
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
            <div style={{ marginTop: 8, padding: 10, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
              <div style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Calendar risk</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 4 }}>
                <StatusBadge tone={riskTone(activeRiskCalendar)}>
                  {activeRiskCalendar?.decision?.decision_state ?? "normal"}
                </StatusBadge>
                <StatusBadge tone="neutral">{activeRiskCalendar?.decision?.risk_level ?? "normal"}</StatusBadge>
                <span style={{ color: "var(--op-muted, #7a8999)" }}>Action: {activeRiskCalendar?.decision?.recommended_action ?? "trade_normally"}</span>
              </div>
              <div style={{ marginTop: 6, color: activeRiskCalendar?.decision?.allow_new_entries === false ? "var(--op-warn, #f2a03f)" : "var(--op-muted, #7a8999)" }}>
                {activeRiskCalendar?.decision?.allow_new_entries === false
                  ? "Sit this one out unless the deterministic risk gate clears."
                  : activeRiskCalendar?.decision?.warning_summary ?? "No active calendar block on the selected recommendation."}
              </div>
              {activeRiskCalendar?.decision?.requires_confirmation ? (
                <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                  <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={riskCalendarConfirmed}
                      onChange={(event) => setRiskCalendarConfirmed(event.target.checked)}
                    />
                    I reviewed the calendar risk for this paper-only order
                  </label>
                  <label style={{ display: "grid", gap: 4 }}>
                    <span>Confirmation reason</span>
                    <input
                      value={riskCalendarOverrideReason}
                      onChange={(event) => setRiskCalendarOverrideReason(event.target.value)}
                      placeholder="Why staging is still appropriate in paper mode"
                    />
                  </label>
                </div>
              ) : null}
            </div>
            {replayOutcome?.has_stageable_candidate === false ? <div style={{ marginTop: 6, color: "var(--op-warn, #f2a03f)" }}>No paper order can be staged from this replay. {replayOutcome.stageable_reason ?? ""}</div> : null}
          </div>
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}><strong>symbol:</strong> {selected.symbol} · <strong>side:</strong> <StatusBadge tone={selected.side?.toLowerCase() === "buy" ? "good" : "warn"}>{selected.side}</StatusBadge> · <strong>shares:</strong> {selected.shares} · <strong>limit:</strong> {selected.limit_price}</div>
            <div><strong>recommendation id:</strong> <span style={{ fontFamily: "monospace" }}>{selected.recommendation_id}</span> · <strong>replay run id:</strong> <span style={{ fontFamily: "monospace" }}>{selected.replay_run_id ?? "—"}</span></div>
            <div><strong>source:</strong> {selected.fallback_mode ? `fallback (${selected.market_data_source ?? "provider"})` : (selected.market_data_source ?? dataSource)} · <strong>status:</strong> {selected.status}</div>
            <div style={{ color: "var(--op-muted, #7a8999)" }}>
              Recommended {selected.recommended_shares ?? selected.shares} shares · final paper order {selected.final_order_shares ?? selected.shares} shares · estimated notional {selected.estimated_notional != null ? formatDollars(selected.estimated_notional) : formatDollars(selected.shares * selected.limit_price)}
              {selected.notional_cap_reduced ? " · notional cap reduced size" : ""}
            </div>
            <div style={{ color: "var(--op-muted, #7a8999)" }}>
              Estimated round-trip fees (entry + exit) ${selected.estimated_total_fees?.toFixed(2) ?? "0.00"} · paper-only preview
            </div>
          </>
        )}
      </Card>
    ) : null}

    <Card><div className="op-row"><button className={orderDoneForRec ? "op-btn op-btn-secondary" : "op-btn-primary-cta op-btn-pulse"} onClick={() => void stagePaperOrder()} disabled={busy || unsupportedGuidedMode || replayOutcome?.has_stageable_candidate === false}>{busy ? "Staging..." : orderDoneForRec ? "Stage another →" : "Stage paper order now →"}</button><button onClick={() => void load()} disabled={busy}>{busy ? "Refreshing..." : "Refresh order history"}</button></div><InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} /></Card>
    {error ? <ErrorState title="Orders unavailable" hint={error} /> : null}

    <div id="active-position-review">
    <Card title="Active Position Review">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <StatusBadge tone="neutral">Review only</StatusBadge>
        <StatusBadge tone="neutral">No automatic exits</StatusBadge>
        <StatusBadge tone="neutral">Paper position management</StatusBadge>
      </div>
      {positionReviews.length === 0 ? (
        <EmptyState title="No active paper positions to review" hint="Open equity paper positions will appear here with mark-to-market context." />
      ) : (
        <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
          <table className="op-table">
            <thead>
              <tr>
                <th>symbol</th>
                <th>qty</th>
                <th>avg entry</th>
                <th>current mark</th>
                <th><MetricLabel label="unrealized P&L" term="net_pnl" /></th>
                <th>return</th>
                <th>stop / targets</th>
                <th>days</th>
                <th>risk calendar</th>
                <th>recommendation</th>
                <th>action</th>
              </tr>
            </thead>
            <tbody>
              {positionReviews.map((review) => (
                <tr key={review.position_id}>
                  <td>
                    <strong>{review.symbol}</strong>
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>{review.side} | {review.market_session_policy ?? "latest_snapshot"}</div>
                  </td>
                  <td>{review.quantity ?? "Unavailable"}</td>
                  <td>{formatMaybeDollars(review.average_entry_price)}</td>
                  <td>
                    {formatMaybeDollars(review.current_mark_price)}
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                      {review.market_data_fallback_mode ? `fallback (${review.market_data_source ?? "provider"})` : review.market_data_source ?? "provider"} | {formatMarkAsOfTime(review.mark_as_of)}
                    </div>
                  </td>
                  <td>
                    <span style={{ color: review.unrealized_pnl != null ? pnlColor(review.unrealized_pnl) : "inherit", fontWeight: 600 }}>
                      {review.unrealized_pnl != null ? formatSignedDollars(review.unrealized_pnl) : "Unavailable"}
                    </span>
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                      notional {formatMaybeDollars(review.estimated_current_notional)}
                    </div>
                  </td>
                  <td>{formatMaybePercent(review.unrealized_return_pct)}</td>
                  <td>
                    <div>stop {review.stop_price != null ? `${formatMaybeDollars(review.stop_price)} (${formatMaybePercent(review.distance_to_stop_pct)})` : "missing"}</div>
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                      T1 {review.target_1 != null ? `${formatMaybeDollars(review.target_1)} (${formatMaybePercent(review.distance_to_target_1_pct)})` : "missing"} | T2 {review.target_2 != null ? `${formatMaybeDollars(review.target_2)} (${formatMaybePercent(review.distance_to_target_2_pct)})` : "missing"}
                    </div>
                  </td>
                  <td>
                    {review.days_held ?? "Unavailable"}
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>{review.holding_period_status}</div>
                  </td>
                  <td>
                    <StatusBadge tone={riskTone(review.risk_calendar)}>{review.risk_calendar?.decision?.decision_state ?? "normal"}</StatusBadge>
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>{review.risk_calendar?.decision?.risk_level ?? "normal"}</div>
                  </td>
                  <td>
                    <StatusBadge tone={review.current_recommendation_status === "top_candidate" ? "good" : review.current_recommendation_status === "weakened" ? "warn" : "neutral"}>{review.current_recommendation_status}</StatusBadge>
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                      {review.already_open ? "Already open" : "Not open"} | rank {review.current_rank ?? "n/a"}
                    </div>
                  </td>
                  <td>
                    <StatusBadge tone={actionTone(review.action_classification)}>{review.action_classification}</StatusBadge>
                    <div style={{ marginTop: 4, maxWidth: 280, color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>{review.action_summary}</div>
                    {review.missing_data.length ? (
                      <div style={{ marginTop: 4, color: "var(--op-warn, #f2a03f)", fontSize: "0.78rem" }}>
                        Missing: {review.missing_data.join(", ")}
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
    </div>

    <div id="options-position-review">
    <Card title="Options Position Review">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <StatusBadge tone="neutral">Review only</StatusBadge>
        <StatusBadge tone="neutral">No automatic exits</StatusBadge>
        <StatusBadge tone="neutral">No automatic rolling</StatusBadge>
        <StatusBadge tone="neutral">No broker routing</StatusBadge>
        <StatusBadge tone="neutral">Paper position management</StatusBadge>
      </div>
      {optionStructureReviews.length === 0 ? (
        <EmptyState title="No active options structures to review" hint="Open paper-only options structures will appear here with payoff, expiration, leg, and risk-calendar context." />
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {optionStructureReviews.map((review) => (
            <div
              key={review.structure_id}
              className="op-card"
              style={{ padding: 12, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <strong>{review.underlying_symbol}</strong>
                    <StatusBadge tone={optionActionTone(review.action_classification)}>{review.action_classification}</StatusBadge>
                    <StatusBadge tone={review.current_mark_debit_credit == null ? "warn" : "good"}>
                      {review.current_mark_debit_credit == null ? "Mark unavailable" : "Marked"}
                    </StatusBadge>
                  </div>
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem", marginTop: 4 }}>
                    Structure #{review.structure_id} | {formatOptionStructureToken(review.strategy_type)} | {formatOptionStructureToken(review.side)}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div><strong>Expiration:</strong> {review.expiration_date ?? "Unavailable"}</div>
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                    {formatDte(review.days_to_expiration)} | {formatOptionStructureToken(review.expiration_status)}
                  </div>
                </div>
              </div>
              <div className="op-grid-4" style={{ marginTop: 10 }}>
                <div>
                  <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Contracts</div>
                  <strong>{review.contracts ?? "Unavailable"}</strong>
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                    multiplier {review.multiplier_assumption ?? "mixed/unavailable"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Opening debit/credit</div>
                  <strong>{formatOpeningDebitCredit(review)}</strong>
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                    commissions {formatMaybeDollars(review.opening_commissions)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Current estimated mark</div>
                  <strong>
                    {review.current_mark_debit_credit != null
                      ? `${formatOptionStructureToken(review.current_mark_debit_credit_type)} ${formatMaybeDollars(review.current_mark_debit_credit)}`
                      : "Mark unavailable"}
                  </strong>
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                    Net P&L {review.estimated_unrealized_pnl != null ? formatSignedDollars(review.estimated_unrealized_pnl) : "Unavailable"}
                    {review.estimated_unrealized_return_pct != null ? ` | ${review.estimated_unrealized_return_pct.toFixed(2)}%` : ""}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Risk calendar</div>
                  <StatusBadge tone={riskTone(review.risk_calendar)}>
                    {review.risk_calendar?.decision?.decision_state ?? "normal"}
                  </StatusBadge>
                  <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                    {review.risk_calendar?.decision?.risk_level ?? "normal"}
                  </div>
                </div>
              </div>
              <div className="op-grid-4" style={{ marginTop: 10 }}>
                <div><strong><MetricLabel label="Max profit" term="max_profit" />:</strong> {formatMaybeDollars(review.max_profit)}</div>
                <div><strong><MetricLabel label="Max loss" term="max_loss" />:</strong> {formatMaybeDollars(review.max_loss)}</div>
                <div style={{ gridColumn: "span 2" }}><strong><MetricLabel label="Breakevens" term="breakeven" />:</strong> {formatBreakevenList(review.breakevens)}</div>
              </div>
              {review.estimated_unrealized_pnl != null ? (
                <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                  Gross {review.estimated_unrealized_gross_pnl != null ? formatSignedDollars(review.estimated_unrealized_gross_pnl) : "Unavailable"}
                  {" "} | Estimated total commissions {formatMaybeDollars(review.estimated_total_commissions)}
                </div>
              ) : null}
              <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", fontSize: "0.86rem", lineHeight: 1.45 }}>
                {review.action_summary}
              </div>
              {review.payoff_summary ? (
                <div style={{ marginTop: 4, color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                  {review.payoff_summary}
                </div>
              ) : null}
              {review.warnings.length ? (
                <div style={{ marginTop: 8, color: "var(--op-warn, #f2a03f)", fontSize: "0.82rem" }}>
                  Warnings: {review.warnings.join(" ")}
                </div>
              ) : null}
              {review.missing_data.length ? (
                <div style={{ marginTop: 6, color: "var(--op-warn, #f2a03f)", fontSize: "0.78rem" }}>
                  Missing: {review.missing_data.join(", ")}
                </div>
              ) : null}
              <details style={{ marginTop: 10 }}>
                <summary>Leg details</summary>
                <div style={{ marginTop: 6, overflowX: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                  <table className="op-table" style={{ margin: 0 }}>
                    <thead>
                      <tr>
                        <th>leg</th>
                        <th>side</th>
                        <th>type</th>
                        <th>strike</th>
                        <th>expiry</th>
                        <th>contracts</th>
                        <th>opening premium</th>
                        <th>current mark</th>
                        <th>method / source</th>
                        <th>IV / OI</th>
                        <th>Greeks</th>
                        <th><MetricLabel label="leg P&L" term="net_pnl" /></th>
                      </tr>
                    </thead>
                    <tbody>
                      {review.legs.length === 0 ? (
                        <tr><td colSpan={12} style={{ color: "var(--op-muted, #7a8999)" }}>Leg details unavailable.</td></tr>
                      ) : review.legs.map((leg) => (
                        <tr key={leg.leg_id}>
                          <td>
                            #{leg.leg_id}
                            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                              {leg.option_symbol ?? "option symbol unavailable"}
                            </div>
                          </td>
                          <td>{formatOptionStructureToken(leg.side)}</td>
                          <td>{formatOptionStructureToken(leg.option_type)}</td>
                          <td>{leg.strike}</td>
                          <td>{leg.expiration ?? "Unavailable"}</td>
                          <td>{leg.contracts}</td>
                          <td>{formatMaybeDollars(leg.opening_premium)}</td>
                          <td>
                            {leg.current_mark_premium != null ? formatMaybeDollars(leg.current_mark_premium) : "Mark unavailable"}
                            {leg.stale ? (
                              <div style={{ color: "var(--op-warn, #f2a03f)", fontSize: "0.76rem" }}>stale</div>
                            ) : null}
                          </td>
                          <td>
                            {formatOptionStructureToken(leg.mark_method)}
                            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                              {leg.market_data_source ?? "unavailable"} | {formatMarkAsOfTime(leg.mark_as_of)}
                            </div>
                          </td>
                          <td>
                            {formatMaybeIv(leg.implied_volatility)}
                            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                              OI {Number.isFinite(Number(leg.open_interest)) ? Number(leg.open_interest).toLocaleString("en-US") : "unavailable"}
                            </div>
                          </td>
                          <td>
                            <div>Delta {formatMaybeDecimal(leg.delta, 3)} | Gamma {formatMaybeDecimal(leg.gamma, 3)}</div>
                            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                              Theta {formatMaybeDecimal(leg.theta, 3)} | Vega {formatMaybeDecimal(leg.vega, 3)}
                            </div>
                          </td>
                          <td>
                            {leg.estimated_leg_unrealized_pnl != null ? formatSignedDollars(leg.estimated_leg_unrealized_pnl) : "Unavailable"}
                            {leg.missing_data.length ? (
                              <div style={{ color: "var(--op-warn, #f2a03f)", fontSize: "0.76rem" }}>
                                Missing: {leg.missing_data.join(", ")}
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          ))}
        </div>
      )}
    </Card>
    </div>

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
                <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>notional</th>
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
                    <td>{formatDollars(p.open_notional)}</td>
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
                      <td colSpan={8} style={{ background: "var(--card-bg-alt, #0e1822)", padding: 12 }}>
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
          <thead><tr><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>created_at</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>side</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>shares</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>notional</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>limit/fill</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>broker status</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>fill count</th><th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}></th></tr></thead>
          <tbody>
            {orders.length === 0 && !busy ? <tr><td colSpan={9} style={{ color: "#9fb0c3", textAlign: "center", padding: "16px 8px" }}>No paper orders yet. Click "Stage paper order now" above to create your first order.</td></tr> : null}
            {orders.flatMap((o) => {
              const cancelable = o.status === "staged" && (o.fills?.length ?? 0) === 0;
              const rowEls: React.ReactNode[] = [
                <tr key={o.order_id} onClick={() => setSelectedOrderId(o.order_id)} className={`is-selectable ${selectedOrderId === o.order_id ? "is-active" : ""}`}>
                  <td>{o.created_at}</td>
                  <td>{o.symbol}</td>
                  <td><span className={`op-side-badge is-${o.side.toLowerCase()}`}>{o.side}</span></td>
                  <td>{o.shares}</td>
                  <td>{formatDollars(o.estimated_notional ?? (o.shares * o.limit_price))}</td>
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
                    <td colSpan={9} style={{ background: "var(--card-bg-alt, #0e1822)", padding: 12 }}>
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
            <div><strong>Recommended shares:</strong> {selected.recommended_shares ?? selected.shares}</div>
            <div><strong>Estimated notional:</strong> {selected.estimated_notional != null ? formatDollars(selected.estimated_notional) : formatDollars(selected.shares * selected.limit_price)}</div>
            <div><strong>Risk at stop:</strong> {selected.risk_at_stop != null ? formatDollars(selected.risk_at_stop) : "—"}</div>
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
                    <td>
                      {t.entry_price.toFixed(2)} → {t.exit_price != null ? t.exit_price.toFixed(2) : "—"}
                      <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                        {t.entry_notional != null ? formatDollars(t.entry_notional) : formatDollars(t.qty * t.entry_price)}
                      </div>
                    </td>
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
