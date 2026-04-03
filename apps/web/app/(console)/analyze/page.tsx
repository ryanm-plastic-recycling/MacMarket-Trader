"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type AnalyzePayload = {
  symbol: string;
  source: string;
  market_regime: string;
  technical_summary: string;
  strategy_scoreboard: Array<{ strategy: string; score: number }>;
  levels: { support: number[]; resistance: number[]; pivot: number };
  indicator_snapshot: Record<string, string | number>;
  catalyst_summary: string;
  scenarios: Record<string, string>;
  operator_note: string;
};

export default function AnalyzePage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [payload, setPayload] = useState<AnalyzePayload | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });

  async function load() {
    setFeedback({ state: "loading", message: "Analyzing symbol..." });
    const result = await fetchWorkflowApi<AnalyzePayload>(`/api/user/analyze/${symbol}`);
    if (!result.ok || !result.data) {
      setFeedback({ state: "error", message: result.error ?? "Analyze failed" });
      return;
    }
    setPayload(result.data);
    setFeedback({ state: "success", message: "Analyze snapshot ready" });
  }

  useEffect(() => { void load(); }, []);

  return <section className="op-stack">
    <PageHeader title="Symbol Analyze" subtitle="Quick operator summary to decide what matters now before recommendation generation." actions={<StatusBadge tone="neutral">{payload?.source ?? "source pending"}</StatusBadge>} />
    <Card>
      <div className="op-row"><input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} /><button onClick={() => void load()}>Analyze</button></div>
      <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
    </Card>
    {!payload ? <EmptyState title="No symbol snapshot" hint="Run analyze to inspect regime, levels, scenarios, and strategy scoreboard." /> : <>
      <div className="op-grid-2">
        <Card title="Regime + technical summary"><div>{payload.market_regime}</div><div>{payload.technical_summary}</div><div><strong>Catalyst:</strong> {payload.catalyst_summary}</div><div><strong>Operator note:</strong> {payload.operator_note}</div></Card>
        <Card title="Strategy scoreboard"><table className="op-table"><thead><tr><th>Strategy</th><th>Score</th></tr></thead><tbody>{payload.strategy_scoreboard.map((row) => <tr key={row.strategy}><td>{row.strategy}</td><td>{row.score}</td></tr>)}</tbody></table></Card>
      </div>
      <div className="op-grid-3">
        <Card title="Support / resistance"><div>Support: {payload.levels.support.join(" / ")}</div><div>Resistance: {payload.levels.resistance.join(" / ")}</div><div>Pivot: {payload.levels.pivot}</div></Card>
        <Card title="Indicator snapshot">{Object.entries(payload.indicator_snapshot).map(([key, value]) => <div key={key}>{key}: {String(value)}</div>)}</Card>
        <Card title="Bull / Base / Bear">{Object.entries(payload.scenarios).map(([key, value]) => <div key={key}><strong>{key}:</strong> {value}</div>)}</Card>
      </div>
    </>}
  </section>;
}
