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

export default function SchedulesPage() {
  const searchParams = useSearchParams();
  const prefill = useMemo(() => ({
    symbols: (searchParams.get("symbols") ?? "").split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
    name: (searchParams.get("name") ?? "").trim(),
  }), [searchParams]);
  const [rows, setRows] = useState<Schedule[]>([]);
  const [selected, setSelected] = useState<Schedule | null>(null);
  const [name, setName] = useState("Morning strategy scan");
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA");
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [error, setError] = useState<string | null>(null);
  const [marketMode, setMarketMode] = useState<MarketMode>("equities");

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

  useEffect(() => {
    if (prefill.symbols.length) {
      setSymbols(prefill.symbols.join(","));
    }
    if (prefill.name) {
      setName(prefill.name);
    }
  }, [prefill.name, prefill.symbols.join(",")]);

  async function createOrUpdateSchedule(scheduleId?: number) {
    const payload = {
      name,
      frequency: "weekdays",
      run_time: "08:30",
      timezone: "America/New_York",
      market_mode: marketMode,
      symbols: symbols.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
      enabled_strategies: ["Event Continuation", "Breakout / Prior-Day High", "Pullback / Trend Continuation"],
      top_n: 5,
    };
    const result = await fetchWorkflowApi(scheduleId ? `/api/user/strategy-schedules/${scheduleId}` : "/api/user/strategy-schedules", {
      method: scheduleId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
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

  return <section className="op-stack">
    <PageHeader title="Scheduled Strategy Reports" subtitle="Recurring ranked strategy scans with run history and payload summaries." actions={<StatusBadge tone="neutral">EMAIL_PROVIDER=console/local is explicit</StatusBadge>} />
    <Card title="Create / update schedule">
      <div className="op-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Schedule name" />
        <input value={symbols} onChange={(e) => setSymbols(e.target.value)} placeholder="AAPL,MSFT,NVDA" style={{ minWidth: 260 }} />
        <select value={marketMode} onChange={(e) => setMarketMode(e.target.value as MarketMode)}><option value="equities">equities</option><option value="options">options (research preview)</option><option value="crypto">crypto (research preview)</option></select>
        <button onClick={() => void createOrUpdateSchedule()}>Create</button>
        <button onClick={() => selected ? void createOrUpdateSchedule(selected.id) : null} disabled={!selected}>Update selected</button>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
    </Card>
    {error ? <ErrorState title="Schedules unavailable" hint={error} /> : null}
    <div className="op-grid-2">
      <Card title="Active schedules">
        {rows.length === 0 ? <EmptyState title="No schedules" hint="Create a schedule to start recurring ranked scans." /> : (
          <table className="op-table">
            <thead><tr><th>Name</th><th>Config</th><th>Last/Next</th><th>Latest summary</th><th>Actions</th></tr></thead>
            <tbody>{rows.map((row) => <tr key={row.id} className={`is-selectable ${selected?.id === row.id ? "is-active" : ""}`} onClick={() => setSelected(row)}>
              <td>{row.name}<br /><StatusBadge tone={row.enabled ? "good" : "warn"}>{row.latest_status}</StatusBadge></td>
              <td>{row.frequency} @ {row.run_time} {row.timezone}<br />{row.config_summary?.market_mode ?? row.payload?.market_mode} · {(row.payload?.symbols ?? []).join(", ")}</td>
              <td>{row.latest_run_at ?? "-"}<br />{row.next_run_at ?? "-"}</td>
              <td>top {row.latest_payload_summary?.top_candidate_count ?? 0} · watch {row.latest_payload_summary?.watchlist_count ?? 0} · no-trade {row.latest_payload_summary?.no_trade_count ?? 0}</td>
              <td className="op-row"><button onClick={() => void toggleSchedule(row)}>{row.enabled ? "Disable" : "Enable"}</button><button onClick={() => void runNow(row.id)}>Run now</button></td>
            </tr>)}</tbody>
          </table>
        )}
      </Card>
      <Card title="Selected schedule run history">
        {!selected ? <EmptyState title="Select a schedule" hint="Click a schedule row to inspect recent run outcomes." /> : (
          <>
            <div><strong>delivery target:</strong> {selected.config_summary?.delivery_target ?? selected.payload?.email_delivery_target ?? "-"}</div>
            <div><strong>top_n:</strong> {selected.config_summary?.top_n ?? selected.payload?.top_n ?? 5}</div>
            <table className="op-table"><thead><tr><th>run</th><th>status</th><th>delivered_to</th><th>summary</th></tr></thead><tbody>{(selected.history ?? []).map((run) => <tr key={run.id}><td>{run.created_at}</td><td>{run.status}</td><td>{run.delivered_to}</td><td>top {run.summary?.top_candidate_count ?? 0} / watch {run.summary?.watchlist_count ?? 0} / no-trade {run.summary?.no_trade_count ?? 0}</td></tr>)}</tbody></table>
          </>
        )}
      </Card>
    </div>
  </section>;
}
