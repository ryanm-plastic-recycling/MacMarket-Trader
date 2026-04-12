"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";
import { buildIndicatorProvenance, strategyFitText } from "@/lib/analyze-helpers";

type ScoreboardEntry = {
  rank: number;
  strategy: string;
  status: string;
  score: number;
  expected_rr: number;
  confidence: number;
  reason_text: string;
  thesis?: string;
  score_breakdown?: Record<string, number>;
};

type AnalyzePayload = {
  symbol: string;
  market_mode: string;
  timeframe: string;
  source: string;
  market_regime: string;
  technical_summary: string;
  strategy_scoreboard: ScoreboardEntry[];
  levels: { support: number[]; resistance: number[]; pivot: number };
  indicator_snapshot: Record<string, string | number>;
  catalyst_summary: string;
  scenarios: Record<string, string>;
  operator_note: string;
  next_actions: Array<{ label: string; path: string }>;
};

export default function AnalyzePage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [payload, setPayload] = useState<AnalyzePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });

  async function load() {
    setFeedback({ state: "loading", message: "Running fast symbol triage…" });
    const result = await fetchWorkflowApi<AnalyzePayload>(`/api/user/analyze/${symbol}`);
    if (!result.ok || !result.data) {
      setError(result.error ?? "Analyze failed");
      setFeedback({ state: "error", message: result.error ?? "Analyze failed" });
      return;
    }
    setError(null);
    setPayload(result.data);
    setFeedback({ state: "success", message: "Analyze triage ready." });
  }

  useEffect(() => { void load(); }, []);

  return <section className="op-stack">
    <PageHeader title="Symbol Analyze" subtitle="Fast triage workspace that complements Strategy Workbench." actions={<StatusBadge tone="neutral">{payload?.source ?? "source pending"}</StatusBadge>} />
    <Card>
      <div className="op-row"><input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === "Enter" && void load()} /><button onClick={() => void load()}>Analyze</button></div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
    </Card>
    {error ? <ErrorState title="Analyze unavailable" hint={error} /> : null}
    {!payload ? <EmptyState title="No symbol snapshot" hint="Run analyze to inspect triage scoreboard and next actions." /> : <>
      <div className="op-grid-3">
        <Card title="Mode / timeframe / regime"><div><strong>mode:</strong> {payload.market_mode}</div><div><strong>timeframe:</strong> {payload.timeframe}</div><div><strong>regime:</strong> {payload.market_regime}</div><div>{payload.technical_summary}</div></Card>
        <Card title="Levels"><div>Support: {payload.levels.support.join(" / ")}</div><div>Resistance: {payload.levels.resistance.join(" / ")}</div><div>Pivot: {payload.levels.pivot}</div></Card>
        <Card title="Indicator snapshot">{buildIndicatorProvenance(payload.indicator_snapshot).map((item) => <div key={item.key} className="op-row" style={{ gap: 6 }}><StatusBadge tone={item.tone}>{item.label}</StatusBadge><span>{item.display}</span></div>)}</Card>
      </div>
      <Card title="Ranked strategy scoreboard">
        <table className="op-table">
          <thead><tr><th>rank</th><th>strategy</th><th>status</th><th>score</th><th>rr</th><th>conf</th><th>fit factors</th></tr></thead>
          <tbody>{payload.strategy_scoreboard.map((row) => <tr key={`${row.rank}-${row.strategy}`}>
            <td>{row.rank}</td>
            <td>
              <div>{row.strategy}</div>
              {row.reason_text ? <div style={{ fontSize: "0.8em", opacity: 0.7, marginTop: 2 }}>{row.reason_text}</div> : null}
              {row.thesis ? <div style={{ fontSize: "0.75em", opacity: 0.6, marginTop: 2, fontStyle: "italic" }}>{row.thesis}</div> : null}
            </td>
            <td>{row.status}</td>
            <td>{row.score}</td>
            <td>{row.expected_rr}</td>
            <td>{row.confidence}</td>
            <td style={{ fontSize: "0.8em", opacity: 0.75 }}>{row.score_breakdown ? strategyFitText(row.score_breakdown) : "—"}</td>
          </tr>)}</tbody>
        </table>
      </Card>
      <div className="op-grid-2">
        <Card title="Scenarios">{Object.entries(payload.scenarios).map(([key, value]) => <div key={key}><strong>{key}:</strong> {value}</div>)}</Card>
        <Card title="What to do next"><div>{payload.operator_note}</div><div className="op-row" style={{ marginTop: 8 }}>{payload.next_actions.map((action) => {
          const path = action.path.includes("/recommendations")
            ? `${action.path}${action.path.includes("?") ? "&" : "?"}symbols=${payload.symbol}`
            : action.path;
          return <button key={action.label} onClick={() => window.location.assign(path)}>{action.label}</button>;
        })}</div></Card>
      </div>
    </>}
  </section>;
}
