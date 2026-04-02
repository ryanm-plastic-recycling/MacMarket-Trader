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
    <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 12 }}>
      <table style={{ width: "100%", fontSize: 13 }}><thead><tr><th>symbol</th><th>thesis</th><th>entry</th><th>invalidation</th><th>R/R</th><th>confidence</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id} onClick={() => setSelected(r)} style={{ cursor: "pointer" }}><td>{r.symbol}</td><td>{r.payload?.thesis}</td><td>{r.payload?.entry?.zone_low}/{r.payload?.entry?.zone_high}</td><td>{r.payload?.invalidation?.price}</td><td>{r.payload?.quality?.expected_rr}</td><td>{r.payload?.quality?.confidence}</td></tr>)}</tbody></table>
      <div style={{ border: "1px solid #2a3440", background: "#111922", padding: 12 }}>
        <h3 style={{ marginTop: 0 }}>Actionable detail pane</h3>
        <div><strong>Symbol:</strong> {selected?.symbol ?? "-"}</div>
        <div><strong>Catalyst:</strong> {selected?.payload?.catalyst?.type ?? "-"}</div>
        <div><strong>Thesis:</strong> {selected?.payload?.thesis ?? "-"}</div>
        <div><strong>Entry zone:</strong> {selected?.payload?.entry?.zone_low ?? "-"} - {selected?.payload?.entry?.zone_high ?? "-"}</div>
        <div><strong>Trigger:</strong> {selected?.payload?.entry?.trigger ?? "-"}</div>
        <div><strong>Invalidation:</strong> {selected?.payload?.invalidation?.price ?? "-"} ({selected?.payload?.invalidation?.reason ?? "-"})</div>
        <div><strong>Targets:</strong> T1 {selected?.payload?.targets?.target_1 ?? "-"} / T2 {selected?.payload?.targets?.target_2 ?? "-"}</div>
        <div><strong>Operator notes:</strong> {(selected?.payload?.evidence?.explanatory_notes ?? []).join(" | ") || "No notes"}</div>
      </div>
    </div>
  </section>;
}
