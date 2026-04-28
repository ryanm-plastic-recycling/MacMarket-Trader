// Helpers for the /orders close-trade lifecycle UI.

export function pnlColor(pnl: number): string {
  if (pnl > 0) return "#21c06e";
  if (pnl < 0) return "#e07a7a";
  return "inherit";
}

// Format a hold duration in seconds as a compact human string.
//   < 60s         → "<1m"
//   < 60m         → "Nm"
//   < 24h         → "Nh Mm"
//   ≥ 24h         → "Nd Mh"
// Negative or null inputs return "—".
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

// Format an ISO timestamp as "Nh ago" / "Nm ago" / "Nd ago" relative to `now` (defaults to Date.now()).
// Returns the original ISO string on parse failure or for future-dated inputs.
export function formatRelativeTime(iso: string | null | undefined, nowMs: number = Date.now()): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  const deltaSec = Math.floor((nowMs - t) / 1000);
  if (deltaSec < 0) return iso;
  if (deltaSec < 60) return "just now";
  const minutes = Math.floor(deltaSec / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
