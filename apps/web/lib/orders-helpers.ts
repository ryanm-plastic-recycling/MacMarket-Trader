// Helpers for the /orders close-trade lifecycle UI.

export function pnlColor(pnl: number): string {
  if (pnl > 0) return "#21c06e";
  if (pnl < 0) return "#e07a7a";
  return "inherit";
}

// Format a hold duration in seconds as a compact human string.
//   < 60s -> "<1m"
//   < 60m -> "Nm"
//   < 24h -> "Nh Mm"
//   >= 24h -> "Nd Mh"
// Negative or null inputs return an em dash.
export function formatHoldDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.floor(seconds);
  if (total < 60) return "<1m";
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const remM = minutes - hours * 60;
    return remM > 0 ? `${hours}h ${remM}m` : `${hours}h`;
  }
  const days = Math.floor(hours / 24);
  const remH = hours - days * 24;
  return remH > 0 ? `${days}d ${remH}h` : `${days}d`;
}

// Pass 4 reopen-undo helpers: the operator can undo a paper close within
// REOPEN_WINDOW_SECONDS of the trade's closed_at timestamp. After that, the
// realized P&L is treated as final and the Reopen button must disappear.

export const REOPEN_WINDOW_SECONDS = 5 * 60;

// Seconds remaining in the reopen window (0 if the window has expired or the
// closed_at timestamp is missing/invalid). `nowMs` is injectable for tests.
export function reopenSecondsRemaining(
  closedAt: string | null | undefined,
  nowMs: number = Date.now(),
): number {
  if (!closedAt) return 0;
  const t = Date.parse(closedAt);
  if (!Number.isFinite(t)) return 0;
  const elapsedSec = Math.floor((nowMs - t) / 1000);
  if (elapsedSec < 0) return REOPEN_WINDOW_SECONDS;
  const remaining = REOPEN_WINDOW_SECONDS - elapsedSec;
  return remaining > 0 ? remaining : 0;
}

// True iff the trade can still be reopened (closed_at is within the window).
export function canReopenTrade(
  closedAt: string | null | undefined,
  nowMs: number = Date.now(),
): boolean {
  return reopenSecondsRemaining(closedAt, nowMs) > 0;
}

type RelativeTimeInput = string | number | null | undefined;

function parseTimestampMs(value: RelativeTimeInput): number | null {
  if (value == null) return null;
  if (typeof value === "number") {
    if (!Number.isFinite(value) || value <= 0) return null;
    return value < 1_000_000_000_000 ? value * 1000 : value;
  }
  const trimmed = value.trim();
  if (!trimmed) return null;
  const numeric = Number(trimmed);
  if (Number.isFinite(numeric)) {
    if (numeric <= 0) return null;
    return numeric < 1_000_000_000_000 ? numeric * 1000 : numeric;
  }
  const parsed = Date.parse(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatTimestampLabel(timestampMs: number, nowMs: number, futureLabel: string): string {
  const deltaSec = Math.floor((nowMs - timestampMs) / 1000);
  if (deltaSec < 0) return futureLabel;
  if (deltaSec < 60) return "just now";
  const minutes = Math.floor(deltaSec / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatRelativeTime(value: RelativeTimeInput, nowMs: number = Date.now()): string {
  if (value == null || value === "") return "—";
  const t = parseTimestampMs(value);
  if (t == null) return String(value);
  return formatTimestampLabel(t, nowMs, String(value));
}

export function formatMarkAsOfTime(value: RelativeTimeInput, nowMs: number = Date.now()): string {
  const t = parseTimestampMs(value);
  if (t == null) return "mark time unavailable";
  if (t < Date.UTC(2000, 0, 1)) return "mark time unavailable";
  if (t > nowMs) return new Date(t).toISOString().replace("T", " ").slice(0, 16) + " UTC";
  return formatTimestampLabel(t, nowMs, "mark time unavailable");
}
