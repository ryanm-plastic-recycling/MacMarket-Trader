"use client";
import { useEffect, useState } from "react";

type Run = { id: number; symbol: string; created_at: string; recommendation_count: number; approved_count: number; fill_count: number };
type Step = { id: number; step_index: number; recommendation_id: string; approved: boolean; pre_step_snapshot: any; post_step_snapshot: any };

export default function Page() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  useEffect(() => { fetch("/api/user/replay-runs", { cache: "no-store" }).then((r) => r.json()).then(setRuns); }, []);
  async function selectRun(id: number) { const s = await fetch(`/api/user/replay-runs/${id}/steps`, { cache: "no-store" }).then((r) => r.json()); setSteps(s); }

  return <section><h1>Replay runs</h1>
    <table><tbody>{runs.map((r) => <tr key={r.id} onClick={() => selectRun(r.id)}><td>{r.created_at}</td><td>{r.symbol}</td><td>{r.recommendation_count}</td><td>{r.approved_count}</td><td>{r.fill_count}</td></tr>)}</tbody></table>
    <h3>Steps</h3>
    {steps.map((s) => <div key={s.id}>#{s.step_index} {s.recommendation_id} approved={String(s.approved)} preHeat={s.pre_step_snapshot?.current_heat} postHeat={s.post_step_snapshot?.current_heat}</div>)}
  </section>;
}
