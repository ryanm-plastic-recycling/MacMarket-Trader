"use client";

import { useEffect, useState } from "react";

type Rec = { id: number; created_at: string; symbol: string; payload: any };

export default function Page() {
  const [rows, setRows] = useState<Rec[]>([]);
  const [selected, setSelected] = useState<Rec | null>(null);

  useEffect(() => {
    fetch("/api/user/recommendations", { cache: "no-store" }).then((r) => r.json()).then((data: Rec[]) => {
      setRows(data);
      setSelected(data[0] ?? null);
    });
  }, []);

  return <section style={{ display: "grid", gap: 12 }}>
    <h1>Recommendations</h1>
    <table><thead><tr><th>created_at</th><th>symbol</th><th>side</th><th>setup</th><th>approved/no-trade</th><th>expected_rr</th><th>confidence</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.id} onClick={() => setSelected(r)}><td>{r.created_at}</td><td>{r.symbol}</td><td>{r.payload?.side}</td><td>{r.payload?.entry?.setup_type}</td><td>{r.payload?.approved ? "approved" : "no-trade"}</td><td>{r.payload?.quality?.expected_rr}</td><td>{r.payload?.quality?.confidence}</td></tr>)}</tbody>
    </table>
    <div style={{ border: "1px solid #2a3440", padding: 12 }}>
      <h3>Detail</h3>
      <div>Thesis: {selected?.payload?.thesis ?? "-"}</div>
      <div>Catalyst: {selected?.payload?.catalyst?.type ?? "-"}</div>
      <div>Invalidation: {selected?.payload?.invalidation?.reason ?? "-"}</div>
      <div>Targets: {selected?.payload?.targets?.target_1 ?? "-"} / {selected?.payload?.targets?.target_2 ?? "-"}</div>
      <div>Evidence notes: {(selected?.payload?.evidence?.explanatory_notes ?? []).join(" | ")}</div>
    </div>
  </section>;
}
