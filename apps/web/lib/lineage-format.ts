// Human-readable workflow lineage breadcrumbs for the guided flow.
//
// Replaces raw "rec_a65757eb8d23 → 25 → —" with operator-readable text
// like "AAPL Event Continuation · Rec #a65757 → Replay #25 → Order pending".

import type { GuidedFlowState } from "@/lib/guided-workflow";

export type LineageSelection = {
  symbol?: string | null;
  strategy?: string | null;
  recommendationId?: string | null;
  // Pass 4 — operator-readable label from the backend. When present, the
  // breadcrumb shows it verbatim instead of the auto-shortened "Rec #xxxxxx".
  recommendationDisplayId?: string | null;
  replayRunId?: string | number | null;
  orderId?: string | null;
};

// Take the last 6 chars of the rec_id hex tail and prefix with "Rec #".
//   "rec_a65757eb8d23" → "Rec #757eb8" — last 6 hex chars after the underscore
// Per spec wording "last 6 chars of the rec_id hex portion": we keep the
// rightmost 6 characters of whatever follows the prefix, which is what
// short-id displays elsewhere in the console.
export function shortRecommendationId(recId: string | null | undefined): string {
  if (!recId) return "—";
  const trimmed = String(recId).trim();
  if (!trimmed) return "—";
  const hex = trimmed.startsWith("rec_") ? trimmed.slice(4) : trimmed;
  if (hex.length <= 6) return `Rec #${hex}`;
  return `Rec #${hex.slice(-6)}`;
}

export function shortReplayRunId(runId: string | number | null | undefined): string {
  if (runId == null || runId === "") return "Replay pending";
  return `Replay #${runId}`;
}

export function shortOrderId(orderId: string | null | undefined): string {
  if (!orderId) return "Order pending";
  const trimmed = String(orderId).trim();
  if (!trimmed) return "Order pending";
  const hex = trimmed.startsWith("ord_") ? trimmed.slice(4) : trimmed;
  if (hex.length <= 6) return `Order #${hex}`;
  return `Order #${hex.slice(-6)}`;
}

// Format the full lineage breadcrumb. Falls back to "—" tokens when fields
// are missing rather than rendering blank gaps in the UI.
export function formatLineageBreadcrumb(
  state: GuidedFlowState | null | undefined,
  selected?: LineageSelection,
): string {
  const symbol = selected?.symbol ?? state?.symbol ?? "—";
  const strategy = selected?.strategy ?? state?.strategy ?? "—";
  const recId = selected?.recommendationId ?? state?.recommendationId ?? null;
  const displayId = selected?.recommendationDisplayId ?? null;
  const runId = selected?.replayRunId ?? state?.replayRunId ?? null;
  const orderId = selected?.orderId ?? state?.orderId ?? null;

  // Prefer the backend-provided display_id when available; fall back to the
  // auto-shortener only when the caller has no display_id to pass through.
  const recLabel = displayId ? displayId : shortRecommendationId(recId);

  const head = `${symbol} ${strategy}`.trim();
  const chain = `${recLabel} → ${shortReplayRunId(runId)} → ${shortOrderId(orderId)}`;
  return `${head} · ${chain}`;
}
