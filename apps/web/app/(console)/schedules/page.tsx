"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { SymbolEntryPreview } from "@/components/symbol-entry-preview";
import { fetchWorkflowApi } from "@/lib/api-client";
import { mergeManualSymbols, parseManualSymbolEntry, SYMBOL_ENTRY_HELP_COPY } from "@/lib/symbol-entry";
import type { MarketMode } from "@/lib/strategy-registry";

function toRelativeTime(dateStr: string | undefined | null): string {
  if (!dateStr) return "Never run";
  const date = new Date(dateStr);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

// Browser timezone (e.g. "America/Indiana/Indianapolis"). Computed once.
const BROWSER_TIMEZONE = (() => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
})();

// Convert a wall-clock (HH:MM) in `tz` on `date` (year/month/day) into the UTC
// instant that produces that wall clock in `tz`. Used so we can re-format the
// same instant in the browser-local zone for the "your time" suffix.
function zonedWallClockToUtc(date: Date, runTime: string, tz: string): Date {
  const [hhRaw, mmRaw] = (runTime ?? "00:00").split(":");
  const hh = Number.isFinite(Number(hhRaw)) ? Number(hhRaw) : 0;
  const mm = Number.isFinite(Number(mmRaw)) ? Number(mmRaw) : 0;
  const candidate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), hh, mm));
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(candidate);
  const map: Record<string, string> = {};
  for (const p of parts) if (p.type !== "literal") map[p.type] = p.value;
  const tzClockMs = Date.UTC(
    Number(map.year), Number(map.month) - 1, Number(map.day),
    Number(map.hour) % 24, Number(map.minute), Number(map.second ?? 0),
  );
  const offsetMs = tzClockMs - candidate.getTime();
  return new Date(candidate.getTime() - offsetMs);
}

// "08:30 CT · 9:30 AM your time". When the stored timezone matches the browser
// timezone, the redundant "your time" suffix is omitted.
function formatScheduleTime(runTime: string | undefined | null, tz: string | undefined | null): string {
  if (!runTime || !tz) return "—";
  let instant: Date;
  try {
    instant = zonedWallClockToUtc(new Date(), runTime, tz);
  } catch {
    return `${runTime} ${tz}`;
  }
  const stored = (() => {
    try {
      return new Intl.DateTimeFormat("en-US", {
        timeZone: tz, hour: "numeric", minute: "2-digit", hour12: true, timeZoneName: "short",
      }).format(instant);
    } catch {
      return `${runTime} ${tz}`;
    }
  })();
  if (tz === BROWSER_TIMEZONE) return stored;
  const local = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", hour12: true }).format(instant);
  return `${stored} · ${local} your time`;
}

// Format an ISO timestamp (e.g. next_run_at from the backend) in the schedule's
// stored timezone alongside the browser-local rendering.
//   "Tue 8:30 AM CT · 9:30 AM your time"
function formatNextRunAt(iso: string | undefined | null, tz: string | undefined | null): string {
  if (!iso) return "—";
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return iso;
  const tzZone = tz || BROWSER_TIMEZONE;
  let stored: string;
  try {
    stored = new Intl.DateTimeFormat("en-US", {
      timeZone: tzZone,
      weekday: "short",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZoneName: "short",
    }).format(instant);
  } catch {
    return instant.toLocaleString();
  }
  if (!tz || tz === BROWSER_TIMEZONE) return stored;
  const local = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", hour12: true }).format(instant);
  return `${stored} · ${local} your time`;
}

type Schedule = {
  id: number;
  name: string;
  frequency: string;
  run_time: string;
  timezone: string;
  enabled: boolean;
  latest_status: string;
  latest_run_at?: string;
  next_run_at?: string;
  payload?: { symbols?: string[]; enabled_strategies?: string[]; top_n?: number; email_delivery_target?: string; market_mode?: string };
  config_summary?: { market_mode: string; symbols_count: number; strategy_count: number; top_n: number; delivery_target: string };
  latest_payload_summary?: { top_candidate_count: number; watchlist_count: number; no_trade_count: number } | null;
  history?: Array<{ id: number; status: string; delivered_to: string; created_at: string; email_provider?: string; summary?: { top_candidate_count?: number; watchlist_count?: number; no_trade_count?: number } }>;
};

type RunCandidate = {
  rank: number;
  symbol: string;
  strategy: string;
  score: number;
  thesis: string;
  entry_zone: string;
  expected_rr: number;
  confidence: number;
  reason_text: string;
};

type RunDetail = {
  id: number;
  schedule_id: number;
  status: string;
  delivered_to: string;
  created_at: string;
  trigger?: string;
  ran_at?: string;
  source?: string;
  top_candidates: RunCandidate[];
  watchlist_only: RunCandidate[];
  no_trade: Array<{ symbol: string; strategy: string; reason_text: string }>;
  summary: { top_candidate_count?: number; watchlist_count?: number; no_trade_count?: number };
};

type Watchlist = { id: number; name: string; symbols: string[]; created_at: string };
type WatchlistSort = "name" | "symbol_count";
type WatchlistSaveMode = "replace" | "merge";

function formatDateOrDash(value: string | undefined | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

const TIMEZONES: { value: string; label: string }[] = [
  // US Eastern
  { value: "America/New_York",             label: "Eastern (ET) — New York" },
  { value: "America/Indiana/Indianapolis", label: "Eastern (ET) — Indianapolis" },
  { value: "America/Detroit",              label: "Eastern (ET) — Detroit" },
  // US Central
  { value: "America/Chicago",              label: "Central (CT) — Chicago" },
  { value: "America/Menominee",            label: "Central (CT) — Menominee" },
  // US Mountain
  { value: "America/Denver",               label: "Mountain (MT) — Denver" },
  { value: "America/Phoenix",              label: "Mountain (no DST) — Phoenix" },
  // US Pacific
  { value: "America/Los_Angeles",          label: "Pacific (PT) — Los Angeles" },
  // US Other
  { value: "America/Anchorage",            label: "Alaska (AKT)" },
  { value: "America/Honolulu",             label: "Hawaii (HT)" },
  // International
  { value: "Europe/London",                label: "London (GMT/BST)" },
  { value: "Europe/Paris",                 label: "Paris/Berlin (CET)" },
  { value: "Asia/Tokyo",                   label: "Tokyo (JST)" },
  { value: "Asia/Hong_Kong",               label: "Hong Kong (HKT)" },
  { value: "UTC",                          label: "UTC" },
];

export default function SchedulesPage() {
  const searchParams = useSearchParams();
  const createFormRef = useRef<HTMLDivElement | null>(null);
  const prefill = useMemo(() => ({
    symbols: parseManualSymbolEntry(searchParams.get("symbols") ?? "").symbols,
    name: (searchParams.get("name") ?? "").trim(),
  }), [searchParams]);

  const [rows, setRows] = useState<Schedule[]>([]);
  const [selected, setSelected] = useState<Schedule | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("Morning strategy scan");
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA");
  const [marketMode, setMarketMode] = useState<MarketMode>("equities");
  const [frequency, setFrequency] = useState("weekdays");
  const [runTime, setRunTime] = useState("08:30");
  const [timezone, setTimezone] = useState("America/Indiana/Indianapolis");
  const [emailTarget, setEmailTarget] = useState("");
  const [topN, setTopN] = useState(5);

  // Watchlist state
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [wlName, setWlName] = useState("My Watchlist");
  const [wlSymbols, setWlSymbols] = useState("");
  const [editingWlId, setEditingWlId] = useState<number | null>(null);
  const [watchlistSaveMode, setWatchlistSaveMode] = useState<WatchlistSaveMode>("replace");
  const [wlFeedback, setWlFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [watchlistQuery, setWatchlistQuery] = useState("");
  const [watchlistSort, setWatchlistSort] = useState<WatchlistSort>("name");
  const [watchlistSymbolFilters, setWatchlistSymbolFilters] = useState<Record<number, string>>({});

  // Run detail state
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [runDetailFeedback, setRunDetailFeedback] = useState<{ state: "idle" | "loading" | "error"; message: string }>({ state: "idle", message: "" });
  const parsedScheduleSymbols = useMemo(() => parseManualSymbolEntry(symbols), [symbols]);
  const parsedWatchlistSymbols = useMemo(() => parseManualSymbolEntry(wlSymbols), [wlSymbols]);
  const editingWatchlist = useMemo(
    () => watchlists.find((wl) => wl.id === editingWlId) ?? null,
    [editingWlId, watchlists],
  );
  const mergedWatchlistSymbols = useMemo(
    () => editingWatchlist ? mergeManualSymbols(editingWatchlist.symbols, parsedWatchlistSymbols) : null,
    [editingWatchlist, parsedWatchlistSymbols],
  );
  const watchlistSubmitSymbols = editingWatchlist && watchlistSaveMode === "merge" && mergedWatchlistSymbols
    ? mergedWatchlistSymbols.symbols
    : parsedWatchlistSymbols.symbols;
  const visibleWatchlists = useMemo(() => {
    const query = watchlistQuery.trim().toUpperCase();
    const rowsWithSymbols = watchlists.map((wl) => {
      const parsed = parseManualSymbolEntry((wl.symbols ?? []).join(","));
      return { wl, parsed };
    });
    const filtered = query
      ? rowsWithSymbols.filter(({ wl, parsed }) => {
          const nameMatch = wl.name.toUpperCase().includes(query);
          const symbolMatch = parsed.symbols.some((symbol) => symbol.includes(query));
          return nameMatch || symbolMatch;
        })
      : rowsWithSymbols;
    return [...filtered].sort((a, b) => {
      if (watchlistSort === "symbol_count") {
        const countDelta = b.parsed.symbols.length - a.parsed.symbols.length;
        if (countDelta !== 0) return countDelta;
      }
      return a.wl.name.localeCompare(b.wl.name);
    });
  }, [watchlistQuery, watchlistSort, watchlists]);

  async function load() {
    setFeedback({ state: "loading", message: "Loading schedules..." });
    const result = await fetchWorkflowApi<Schedule>("/api/user/strategy-schedules");
    if (!result.ok) {
      setError(result.error ?? "Load failed");
      setFeedback({ state: "error", message: result.error ?? "Load failed" });
      return;
    }
    setError(null);
    setRows(result.items);
    setSelected((prev) => result.items.find((item) => item.id === prev?.id) ?? result.items[0] ?? null);
    setFeedback({ state: "success", message: "Schedules loaded" });
  }

  async function loadWatchlists() {
    const result = await fetchWorkflowApi<Watchlist>("/api/user/watchlists");
    if (result.ok) setWatchlists(result.items);
  }

  async function saveWatchlist() {
    setWlFeedback({ state: "loading", message: "Saving..." });
    const body = {
      name: wlName.trim() || "My Watchlist",
      symbols: watchlistSubmitSymbols,
    };
    const url = editingWlId ? `/api/user/watchlists/${editingWlId}` : "/api/user/watchlists";
    const result = await fetchWorkflowApi(url, {
      method: editingWlId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!result.ok) { setWlFeedback({ state: "error", message: result.error ?? "Save failed" }); return; }
    setWlFeedback({ state: "success", message: editingWlId ? "Watchlist updated" : "Watchlist created" });
    setEditingWlId(null);
    setWatchlistSaveMode("replace");
    setWlName("My Watchlist");
    setWlSymbols("");
    await loadWatchlists();
  }

  async function deleteWatchlist(id: number) {
    setWlFeedback({ state: "loading", message: "Deleting..." });
    const result = await fetchWorkflowApi(`/api/user/watchlists/${id}`, { method: "DELETE" });
    if (!result.ok) { setWlFeedback({ state: "error", message: result.error ?? "Delete failed" }); return; }
    setWlFeedback({ state: "success", message: "Watchlist deleted" });
    await loadWatchlists();
  }

  async function removeWatchlistSymbol(wl: Watchlist, symbol: string) {
    const parsed = parseManualSymbolEntry((wl.symbols ?? []).join(","));
    const nextSymbols = parsed.symbols.filter((item) => item !== symbol);
    if (nextSymbols.length === parsed.symbols.length) return;
    if (!nextSymbols.length) {
      setWlFeedback({ state: "error", message: "Watchlists need at least one symbol. Delete the watchlist instead." });
      return;
    }
    setWlFeedback({ state: "loading", message: `Removing ${symbol}...` });
    const result = await fetchWorkflowApi<Watchlist>(`/api/user/watchlists/${wl.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbols: nextSymbols }),
    });
    if (!result.ok) {
      setWlFeedback({ state: "error", message: result.error ?? "Remove failed" });
      return;
    }
    setWatchlists((prev) => prev.map((row) => (
      row.id === wl.id ? { ...row, symbols: result.data?.symbols ?? nextSymbols } : row
    )));
    setWlFeedback({ state: "success", message: `${symbol} removed from ${wl.name}` });
  }

  function startEditWatchlist(wl: Watchlist) {
    setEditingWlId(wl.id);
    setWatchlistSaveMode("replace");
    setWlName(wl.name);
    setWlSymbols(wl.symbols.join(","));
  }

  useEffect(() => { void load(); void loadWatchlists(); }, []);

  // URL prefill: populate name/symbols from query params (create flow from analysis page)
  useEffect(() => {
    if (prefill.symbols.length) setSymbols(prefill.symbols.join(","));
    if (prefill.name) setName(prefill.name);
  }, [prefill.name, prefill.symbols.join(",")]);

  // Pre-populate form from the selected schedule row
  useEffect(() => {
    if (!selected) return;
    // Preserve URL-prefilled name/symbols when in create mode from analysis page
    if (!prefill.name) setName(selected.name);
    if (!prefill.symbols.length) {
      setSymbols((selected.payload?.symbols ?? []).join(","));
      setMarketMode((selected.payload?.market_mode ?? "equities") as MarketMode);
    }
    setFrequency(selected.frequency);
    setRunTime(selected.run_time);
    setTimezone(selected.timezone);
    setEmailTarget(
      selected.config_summary?.delivery_target ??
      selected.payload?.email_delivery_target ??
      "",
    );
    setTopN(selected.config_summary?.top_n ?? selected.payload?.top_n ?? 5);
    setSelectedRunId(null);
    setRunDetail(null);
  }, [selected?.id, prefill.name, prefill.symbols.length]); // eslint-disable-line react-hooks/exhaustive-deps

  async function createOrUpdateSchedule(scheduleId?: number) {
    const scheduleConfig = {
      symbols: parsedScheduleSymbols.symbols,
      enabled_strategies: ["Event Continuation", "Breakout / Prior-Day High", "Pullback / Trend Continuation"],
      top_n: topN,
      market_mode: marketMode,
      ...(emailTarget.trim() ? { email_delivery_target: emailTarget.trim() } : {}),
    };
    // Backend PUT only updates fields in ["name","frequency","run_time","timezone","email_target","enabled","payload"].
    // Symbols/config must be nested under "payload" for updates; POST reads them flat.
    const payload = scheduleId
      ? { name, frequency, run_time: runTime, timezone, payload: scheduleConfig }
      : { name, frequency, run_time: runTime, timezone, ...scheduleConfig };
    const result = await fetchWorkflowApi(
      scheduleId ? `/api/user/strategy-schedules/${scheduleId}` : "/api/user/strategy-schedules",
      {
        method: scheduleId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Save failed" });
      return;
    }
    setFeedback({ state: "success", message: scheduleId ? "Schedule updated" : "Schedule created" });
    await load();
  }

  async function toggleSchedule(schedule: Schedule) {
    await fetchWorkflowApi(`/api/user/strategy-schedules/${schedule.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !schedule.enabled }),
    });
    await load();
  }

  async function runNow(scheduleId: number) {
    setFeedback({ state: "loading", message: "Running schedule now..." });
    const result = await fetchWorkflowApi(`/api/user/strategy-schedules/${scheduleId}/run`, { method: "POST" });
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Run failed" });
      return;
    }
    setFeedback({ state: "success", message: "Schedule run completed." });
    await load();
  }

  async function loadRunDetail(runId: number) {
    if (!selected) return;
    // Toggle off if already expanded
    if (selectedRunId === runId) {
      setSelectedRunId(null);
      setRunDetail(null);
      setRunDetailFeedback({ state: "idle", message: "" });
      return;
    }
    setSelectedRunId(runId);
    setRunDetail(null);
    setRunDetailFeedback({ state: "loading", message: "Loading run detail..." });
    const result = await fetchWorkflowApi<RunDetail>(
      `/api/user/strategy-schedules/${selected.id}/runs/${runId}`,
    );
    if (!result.ok) {
      setRunDetailFeedback({ state: "error", message: result.error ?? "Failed to load run detail" });
      return;
    }
    setRunDetail(result.data);
    setRunDetailFeedback({ state: "idle", message: "" });
  }

  return (
    <section className="op-stack">
      <PageHeader
        title="Scheduled Strategy Reports"
        subtitle="Recurring ranked strategy scans with run history and payload summaries."
        actions={<StatusBadge tone="neutral">EMAIL_PROVIDER=console/local is explicit</StatusBadge>}
      />

      <div ref={createFormRef}><Card title="Create / update schedule">
        <div className="op-row" style={{ alignItems: "flex-start", flexWrap: "wrap" }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Schedule name" />
          <label style={{ display: "grid", gap: 4, minWidth: 300, flex: "1 1 320px" }}>
            <span>Symbols to evaluate</span>
            <textarea
              value={symbols}
              onChange={(e) => setSymbols(e.target.value.toUpperCase())}
              placeholder="SPY, QQQ, AAPL, MSFT"
              rows={2}
              style={{ minWidth: 260, resize: "vertical" }}
            />
          </label>
          {watchlists.length > 0 && (
            <select
              defaultValue=""
              onChange={(e) => {
                const wl = watchlists.find((w) => w.id === Number(e.target.value));
                if (wl) setSymbols(wl.symbols.join(","));
                e.currentTarget.value = "";
              }}
            >
              <option value="" disabled>Apply watchlist…</option>
              {watchlists.map((wl) => (
                <option key={wl.id} value={wl.id}>{wl.name} ({wl.symbols.length})</option>
              ))}
            </select>
          )}
          <select value={marketMode} onChange={(e) => setMarketMode(e.target.value as MarketMode)}>
            <option value="equities">equities</option>
            <option value="options">options (research preview)</option>
            <option value="crypto">crypto (research preview)</option>
          </select>
        </div>
        <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.85rem", lineHeight: 1.5 }}>
          <div>{SYMBOL_ENTRY_HELP_COPY.separators}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.example}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.substitutes}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.temporaryUniverse}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.futureWatchlists}</div>
        </div>
        <SymbolEntryPreview parsed={parsedScheduleSymbols} />
        <div className="op-row">
          <label>
            Frequency&nbsp;
            <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
              <option value="daily">daily</option>
              <option value="weekdays">weekdays</option>
              <option value="weekly">weekly (Monday)</option>
            </select>
          </label>
          <label>
            Run time&nbsp;
            <input type="time" value={runTime} onChange={(e) => setRunTime(e.target.value)} style={{ width: 110 }} />
          </label>
          <label>
            Timezone&nbsp;
            <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {TIMEZONES.map((tz) => <option key={tz.value} value={tz.value}>{tz.label}</option>)}
            </select>
          </label>
        </div>
        <div className="op-row">
          <input
            value={emailTarget}
            onChange={(e) => setEmailTarget(e.target.value)}
            placeholder="Email delivery target (defaults to account email)"
            style={{ minWidth: 300 }}
          />
          <label>
            Top N&nbsp;
            <input
              type="number"
              min={1}
              max={20}
              value={topN}
              onChange={(e) => setTopN(Math.max(1, Math.min(20, Number(e.target.value))))}
              style={{ width: 60 }}
            />
          </label>
          <button onClick={() => void createOrUpdateSchedule()}>Create</button>
          <button onClick={() => selected ? void createOrUpdateSchedule(selected.id) : null} disabled={!selected}>
            Update selected
          </button>
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
      </Card></div>

      <div style={{ fontSize: 12, color: "var(--op-muted, #8b9cb3)" }}>
        Schedule times are stored in the selected timezone. The &ldquo;your time&rdquo; column shows conversion to your browser&rsquo;s local time.
      </div>

      <Card title={editingWlId ? `Edit watchlist: ${wlName}` : "Watchlists"}>
        <div className="op-row" style={{ alignItems: "flex-start", flexWrap: "wrap" }}>
          <input value={wlName} onChange={(e) => setWlName(e.target.value)} placeholder="Watchlist name" />
          <label style={{ display: "grid", gap: 4, minWidth: 300, flex: "1 1 320px" }}>
            <span>Symbols to evaluate</span>
            <textarea
              value={wlSymbols}
              onChange={(e) => setWlSymbols(e.target.value.toUpperCase())}
              placeholder="SPY, QQQ, AAPL, MSFT"
              rows={2}
              style={{ minWidth: 260, resize: "vertical" }}
            />
          </label>
          <button onClick={() => void saveWatchlist()}>{editingWlId ? "Update" : "Create"}</button>
          {editingWlId && (
            <button onClick={() => { setEditingWlId(null); setWatchlistSaveMode("replace"); setWlName("My Watchlist"); setWlSymbols(""); }}>
              Cancel
            </button>
          )}
        </div>
        {editingWlId ? (
          <div style={{ marginTop: 8 }}>
            <div className="op-row" role="radiogroup" aria-label="Watchlist save mode" style={{ flexWrap: "wrap" }}>
              <label>
                <input
                  type="radio"
                  name="watchlist-save-mode"
                  value="replace"
                  checked={watchlistSaveMode === "replace"}
                  onChange={() => setWatchlistSaveMode("replace")}
                />
                &nbsp;Replace current symbols
              </label>
              <label>
                <input
                  type="radio"
                  name="watchlist-save-mode"
                  value="merge"
                  checked={watchlistSaveMode === "merge"}
                  onChange={() => setWatchlistSaveMode("merge")}
                />
                &nbsp;Add to existing symbols
              </label>
            </div>
            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem", lineHeight: 1.45 }}>
              {watchlistSaveMode === "merge" && mergedWatchlistSymbols ? (
                <>
                  <div><strong>Merged preview:</strong> {mergedWatchlistSymbols.symbols.length ? mergedWatchlistSymbols.symbols.join(", ") : "—"}</div>
                  <div>
                    {mergedWatchlistSymbols.symbols.length} symbols · {mergedWatchlistSymbols.addedSymbols.length} new · {mergedWatchlistSymbols.duplicateCount} duplicate{mergedWatchlistSymbols.duplicateCount === 1 ? "" : "s"} ignored
                  </div>
                  {mergedWatchlistSymbols.duplicates.length ? (
                    <div>Merge duplicates ignored: {mergedWatchlistSymbols.duplicates.join(", ")}</div>
                  ) : null}
                </>
              ) : (
                <div>Replace mode: saving overwrites the saved symbol array with the parsed preview below.</div>
              )}
            </div>
          </div>
        ) : null}
        <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.85rem", lineHeight: 1.5 }}>
          <div>{SYMBOL_ENTRY_HELP_COPY.separators}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.example}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.substitutes}</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.providerDiscoveryDeferred}</div>
          <div>Research universe only; watchlists organize symbols for scans and do not send orders.</div>
          <div>Provider metadata may be unavailable; manual symbols can still be saved.</div>
          <div>{SYMBOL_ENTRY_HELP_COPY.futureWatchlists}</div>
          <div>Current lists keep existing symbol-array storage until normalized watchlist management is wired in.</div>
        </div>
        <SymbolEntryPreview parsed={parsedWatchlistSymbols} />
        <InlineFeedback state={wlFeedback.state} message={wlFeedback.message} />
        {watchlists.length === 0 ? (
          <EmptyState title="No watchlists" hint="Create a named symbol list to quickly populate schedule forms." />
        ) : (
          <>
            <div className="op-row" style={{ alignItems: "flex-end", flexWrap: "wrap", margin: "10px 0" }}>
              <label style={{ display: "grid", gap: 4, minWidth: 220 }}>
                <span>Search watchlists</span>
                <input
                  value={watchlistQuery}
                  onChange={(e) => setWatchlistQuery(e.target.value)}
                  placeholder="Filter by name or symbol"
                />
              </label>
              <label>
                Sort watchlists&nbsp;
                <select value={watchlistSort} onChange={(e) => setWatchlistSort(e.target.value as WatchlistSort)}>
                  <option value="name">name</option>
                  <option value="symbol_count">symbol count</option>
                </select>
              </label>
              <StatusBadge tone="neutral">{watchlists.length} saved list{watchlists.length === 1 ? "" : "s"}</StatusBadge>
            </div>
            {visibleWatchlists.length === 0 ? (
              <EmptyState title="No matching watchlists" hint="Adjust the watchlist search to show saved symbol lists." />
            ) : (
              <table className="op-table">
                <thead><tr><th>Name</th><th>Symbol count</th><th>Symbols</th><th>Created</th><th>Actions</th></tr></thead>
                <tbody>
                  {visibleWatchlists.map(({ wl, parsed }) => {
                    const symbolFilter = (watchlistSymbolFilters[wl.id] ?? "").trim().toUpperCase();
                    const shownSymbols = symbolFilter
                      ? parsed.symbols.filter((symbol) => symbol.includes(symbolFilter))
                      : parsed.symbols;
                    return (
                      <tr key={wl.id}>
                        <td>
                          <strong>{wl.name}</strong><br />
                          <span style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>Existing watchlist storage</span>
                        </td>
                        <td><StatusBadge tone="neutral">{parsed.symbols.length} symbol{parsed.symbols.length === 1 ? "" : "s"}</StatusBadge></td>
                        <td style={{ maxWidth: 520 }}>
                          <label style={{ display: "grid", gap: 4, marginBottom: 6 }}>
                            <span style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>Filter symbols in this list</span>
                            <input
                              value={watchlistSymbolFilters[wl.id] ?? ""}
                              onChange={(e) => setWatchlistSymbolFilters((prev) => ({ ...prev, [wl.id]: e.target.value }))}
                              placeholder="Symbol filter"
                              style={{ maxWidth: 220 }}
                            />
                          </label>
                          <div className="op-row" style={{ gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                            {shownSymbols.length ? shownSymbols.map((symbol) => (
                              <span
                                key={symbol}
                                className="op-badge op-badge-neutral"
                                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                              >
                                {symbol}
                                <button
                                  aria-label={`Remove ${symbol} from ${wl.name}`}
                                  onClick={() => void removeWatchlistSymbol(wl, symbol)}
                                  title={`Remove ${symbol}`}
                                  style={{ padding: "0 5px", lineHeight: 1.1 }}
                                >
                                  x
                                </button>
                              </span>
                            )) : <span style={{ color: "var(--text-muted, #8b9cb3)" }}>—</span>}
                          </div>
                          {parsed.duplicateCount ? (
                            <div style={{ marginTop: 6, fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>
                              Duplicate ignored in preview: {parsed.duplicates.join(", ")}
                            </div>
                          ) : null}
                        </td>
                        <td>{formatDateOrDash(wl.created_at)}</td>
                        <td className="op-row">
                          <button onClick={() => setSymbols(parsed.symbols.join(","))}>Apply to form</button>
                          <button onClick={() => startEditWatchlist(wl)}>Edit</button>
                          <button onClick={() => void deleteWatchlist(wl.id)}>Delete</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </>
        )}
      </Card>

      {error ? <ErrorState title="Schedules unavailable" hint={error} /> : null}

      <div className="op-grid-2">
        <Card title="Active schedules">
          {rows.length === 0 ? (
            <div>
              <EmptyState
                title="No scheduled reports yet"
                hint="Scheduled reports rank your watchlist daily and surface top candidates with explicit entry levels, stops, and targets. Create a schedule to get a ranked candidate list on a recurring basis."
              />
              <div className="op-row" style={{ marginTop: 8 }}>
                <button onClick={() => createFormRef.current?.scrollIntoView({ behavior: "smooth" })}>Create your first schedule</button>
              </div>
            </div>
          ) : (
            <table className="op-table">
              <thead>
                <tr><th>Name</th><th>Config</th><th>Last / Next</th><th>Latest summary</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className={`is-selectable ${selected?.id === row.id ? "is-active" : ""}`}
                    onClick={() => setSelected(row)}
                  >
                    <td>
                      {row.name}<br />
                      <StatusBadge tone={row.enabled ? "good" : "warn"}>{row.latest_status}</StatusBadge>
                    </td>
                    <td>
                      {row.frequency} @ {formatScheduleTime(row.run_time, row.timezone)}<br />
                      {row.config_summary?.market_mode ?? row.payload?.market_mode} · {(row.payload?.symbols ?? []).join(", ")}
                    </td>
                    <td>
                      {toRelativeTime(row.latest_run_at ?? row.history?.[0]?.created_at)}<br />
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted, #8b9cb3)" }}>next: {formatNextRunAt(row.next_run_at, row.timezone)}</span>
                    </td>
                    <td>
                      {(row.latest_run_at ?? row.history?.[0]?.created_at)
                        ? <StatusBadge tone={(row.latest_payload_summary?.top_candidate_count ?? 0) > 0 ? "good" : "warn"}>
                            {row.latest_payload_summary?.top_candidate_count ?? 0} top candidate{(row.latest_payload_summary?.top_candidate_count ?? 0) === 1 ? "" : "s"}
                          </StatusBadge>
                        : <span style={{ color: "var(--text-muted, #8b9cb3)" }}>—</span>}
                    </td>
                    <td className="op-row">
                      <button onClick={(e) => { e.stopPropagation(); void toggleSchedule(row); }}>
                        {row.enabled ? "Disable" : "Enable"}
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); void runNow(row.id); }}>
                        Run now
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Selected schedule run history">
          {!selected ? (
            <EmptyState title="Select a schedule" hint="Click a schedule row to inspect recent run outcomes." />
          ) : (
            <>
              <div><strong>delivery target:</strong> {selected.config_summary?.delivery_target ?? selected.payload?.email_delivery_target ?? "-"}</div>
              <div><strong>top_n:</strong> {selected.config_summary?.top_n ?? selected.payload?.top_n ?? 5}</div>
              <table className="op-table">
                <thead>
                  <tr><th>Run</th><th>Status</th><th>Delivery</th><th>Delivered to</th><th>Summary</th></tr>
                </thead>
                <tbody>
                  {(selected.history ?? []).map((run) => (
                    <tr
                      key={run.id}
                      className={`is-selectable ${selectedRunId === run.id ? "is-active" : ""}`}
                      onClick={() => void loadRunDetail(run.id)}
                      title="Click to view run candidates"
                    >
                      <td>{run.created_at}</td>
                      <td>{run.status}</td>
                      <td><StatusBadge tone={run.email_provider === "resend" ? "good" : "neutral"}>{run.email_provider ?? "console"}</StatusBadge></td>
                      <td>{run.delivered_to}</td>
                      <td>{run.summary?.top_candidate_count ?? 0} top · {run.summary?.watchlist_count ?? 0} watch · {run.summary?.no_trade_count ?? 0} no-trade</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {runDetailFeedback.state !== "idle" && (
                <InlineFeedback
                  state={runDetailFeedback.state as "loading" | "error" | "success" | "idle"}
                  message={runDetailFeedback.message}
                />
              )}
            </>
          )}
        </Card>
      </div>

      {runDetail && (
        <Card title={`Run #${runDetail.id} · ${runDetail.trigger ?? "manual"} · ${runDetail.source ?? "-"} · ${runDetail.ran_at ?? runDetail.created_at}`}>
          {runDetail.top_candidates.length > 0 && (
            <>
              <div><strong>Top candidates ({runDetail.top_candidates.length})</strong></div>
              <table className="op-table">
                <thead>
                  <tr><th>#</th><th>Symbol</th><th>Strategy</th><th>Score</th><th>RR</th><th>Entry zone</th><th>Thesis</th><th>Action</th></tr>
                </thead>
                <tbody>
                  {runDetail.top_candidates.map((c) => (
                    <tr key={`${c.symbol}-${c.strategy}-${c.rank}`}>
                      <td>{c.rank}</td>
                      <td><strong>{c.symbol}</strong></td>
                      <td>{c.strategy}</td>
                      <td>{c.score?.toFixed(3) ?? "-"}</td>
                      <td>{c.expected_rr?.toFixed(2) ?? "-"}</td>
                      <td>{c.entry_zone ?? "-"}</td>
                      <td>{c.thesis ?? "-"}</td>
                      <td><Link href={`/analysis?guided=1&symbol=${c.symbol}&strategy=${encodeURIComponent(c.strategy)}`} className="op-btn op-btn-secondary" style={{ whiteSpace: "nowrap" }}>Analyze in guided mode →</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {runDetail.watchlist_only.length > 0 && (
            <>
              <div><strong>Watchlist only ({runDetail.watchlist_only.length})</strong></div>
              <table className="op-table">
                <thead>
                  <tr><th>Symbol</th><th>Strategy</th><th>Score</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {runDetail.watchlist_only.map((c) => (
                    <tr key={`${c.symbol}-${c.strategy}`}>
                      <td>{c.symbol}</td>
                      <td>{c.strategy}</td>
                      <td>{c.score?.toFixed(3) ?? "-"}</td>
                      <td>{c.reason_text ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {runDetail.no_trade.length > 0 && (
            <>
              <div><strong>No-trade ({runDetail.no_trade.length})</strong></div>
              <table className="op-table">
                <thead>
                  <tr><th>Symbol</th><th>Strategy</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {runDetail.no_trade.map((c) => (
                    <tr key={`${c.symbol}-${c.strategy}`}>
                      <td>{c.symbol}</td>
                      <td>{c.strategy}</td>
                      <td>{c.reason_text ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {runDetail.top_candidates.length === 0 && runDetail.watchlist_only.length === 0 && runDetail.no_trade.length === 0 && (
            <EmptyState title="No candidates" hint="This run produced no scored symbols." />
          )}
        </Card>
      )}
    </section>
  );
}
