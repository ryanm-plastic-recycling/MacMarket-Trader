"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";
import type { MarketMode } from "@/lib/strategy-registry";

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
  history?: Array<{ id: number; status: string; delivered_to: string; created_at: string; summary?: { top_candidate_count?: number; watchlist_count?: number; no_trade_count?: number } }>;
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

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "UTC",
];

export default function SchedulesPage() {
  const searchParams = useSearchParams();
  const prefill = useMemo(() => ({
    symbols: (searchParams.get("symbols") ?? "").split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
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
  const [timezone, setTimezone] = useState("America/New_York");
  const [emailTarget, setEmailTarget] = useState("");
  const [topN, setTopN] = useState(5);

  // Run detail state
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [runDetailFeedback, setRunDetailFeedback] = useState<{ state: "idle" | "loading" | "error"; message: string }>({ state: "idle", message: "" });

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

  useEffect(() => { void load(); }, []);

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
    const payload = {
      name,
      frequency,
      run_time: runTime,
      timezone,
      market_mode: marketMode,
      symbols: symbols.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
      enabled_strategies: ["Event Continuation", "Breakout / Prior-Day High", "Pullback / Trend Continuation"],
      top_n: topN,
      ...(emailTarget.trim() ? { email_delivery_target: emailTarget.trim() } : {}),
    };
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

      <Card title="Create / update schedule">
        <div className="op-row">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Schedule name" />
          <input value={symbols} onChange={(e) => setSymbols(e.target.value)} placeholder="AAPL,MSFT,NVDA" style={{ minWidth: 260 }} />
          <select value={marketMode} onChange={(e) => setMarketMode(e.target.value as MarketMode)}>
            <option value="equities">equities</option>
            <option value="options">options (research preview)</option>
            <option value="crypto">crypto (research preview)</option>
          </select>
        </div>
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
              {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
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
      </Card>

      {error ? <ErrorState title="Schedules unavailable" hint={error} /> : null}

      <div className="op-grid-2">
        <Card title="Active schedules">
          {rows.length === 0 ? (
            <EmptyState title="No schedules" hint="Create a schedule to start recurring ranked scans." />
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
                      {row.frequency} @ {row.run_time} {row.timezone}<br />
                      {row.config_summary?.market_mode ?? row.payload?.market_mode} · {(row.payload?.symbols ?? []).join(", ")}
                    </td>
                    <td>{row.latest_run_at ?? "-"}<br />{row.next_run_at ?? "-"}</td>
                    <td>
                      top {row.latest_payload_summary?.top_candidate_count ?? 0} · watch {row.latest_payload_summary?.watchlist_count ?? 0} · no-trade {row.latest_payload_summary?.no_trade_count ?? 0}
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
                  <tr><th>Run</th><th>Status</th><th>Delivered to</th><th>Summary</th></tr>
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
                      <td>{run.delivered_to}</td>
                      <td>top {run.summary?.top_candidate_count ?? 0} / watch {run.summary?.watchlist_count ?? 0} / no-trade {run.summary?.no_trade_count ?? 0}</td>
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
                  <tr><th>#</th><th>Symbol</th><th>Strategy</th><th>Score</th><th>RR</th><th>Entry zone</th><th>Thesis</th></tr>
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
