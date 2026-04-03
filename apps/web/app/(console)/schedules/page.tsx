"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
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
  payload?: { symbols?: string[]; enabled_strategies?: string[]; top_n?: number };
};

export default function SchedulesPage() {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [name, setName] = useState("Morning strategy scan");
  const [symbols, setSymbols] = useState("AAPL,MSFT,NVDA");
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [marketMode, setMarketMode] = useState<MarketMode>("equities");

  async function load() {
    setFeedback({ state: "loading", message: "Loading schedules..." });
    const result = await fetchWorkflowApi<Schedule>("/api/user/strategy-schedules");
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Load failed" });
      return;
    }
    setRows(result.items);
    setFeedback({ state: "success", message: "Schedules loaded" });
  }

  useEffect(() => { void load(); }, []);

  async function createSchedule() {
    const result = await fetchWorkflowApi("/api/user/strategy-schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        frequency: "weekdays",
        run_time: "08:30",
        timezone: "America/New_York",
        market_mode: marketMode,
        symbols: symbols.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
        enabled_strategies: ["Event Continuation", "Breakout / Prior-Day High", "Pullback / Trend Continuation"],
        top_n: 5,
      }),
    });
    if (!result.ok) {
      setFeedback({ state: "error", message: result.error ?? "Create failed" });
      return;
    }
    setFeedback({ state: "success", message: "Schedule created" });
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
    setFeedback({ state: "success", message: "Schedule run completed. Console email payload printed by backend provider." });
    await load();
  }

  return <section className="op-stack">
    <PageHeader title="Scheduled Strategy Reports" subtitle="Recurring ranked strategy scans with deterministic scoring and email delivery." actions={<StatusBadge tone="neutral">EMAIL_PROVIDER=console supported</StatusBadge>} />
    <Card title="Create schedule">
      <div className="op-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Schedule name" />
        <input value={symbols} onChange={(e) => setSymbols(e.target.value)} placeholder="AAPL,MSFT,NVDA" style={{ minWidth: 260 }} />
        <select value={marketMode} onChange={(e) => setMarketMode(e.target.value as MarketMode)}><option value="equities">equities</option><option value="options">options (planned)</option><option value="crypto">crypto (planned)</option></select>
        <button onClick={() => void createSchedule()}>Create schedule</button>
      </div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
    </Card>
    <Card title="Active schedules">
      {rows.length === 0 ? <EmptyState title="No schedules" hint="Create a strategy report schedule to rank candidates and receive recurring emails." /> : (
        <table className="op-table">
          <thead><tr><th>Name</th><th>Symbols</th><th>Strategies</th><th>Frequency</th><th>Last/Next run</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.map((row) => <tr key={row.id}>
              <td>{row.name}</td>
              <td>{(row.payload?.symbols ?? []).join(", ")}</td>
              <td>{(row.payload?.enabled_strategies ?? []).join(" · ")}</td>
              <td>{row.frequency} @ {row.run_time} {row.timezone}</td>
              <td>{row.latest_run_at ?? "-"}<br />{row.next_run_at ?? "-"}</td>
              <td><StatusBadge tone={row.enabled ? "good" : "warn"}>{row.latest_status}</StatusBadge></td>
              <td className="op-row"><button onClick={() => void toggleSchedule(row)}>{row.enabled ? "Disable" : "Enable"}</button><button onClick={() => void runNow(row.id)}>Run now</button></td>
            </tr>)}
          </tbody>
        </table>
      )}
    </Card>
  </section>;
}
