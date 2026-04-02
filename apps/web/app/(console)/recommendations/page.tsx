"use client";

import { useEffect, useState } from "react";

type Rec = { id: number; created_at: string; symbol: string; payload: any; recommendation_id: string };

export default function Page() {
  const [rows, setRows] = useState<Rec[]>([]);
  const [selected, setSelected] = useState<Rec | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    const response = await fetch("/api/user/recommendations", { cache: "no-store" });
    const data = (await response.json()) as Rec[];
    setRows(data);
    setSelected((prev) => data.find((item) => item.id === prev?.id) ?? data[0] ?? null);
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  async function generate() {
    setStatus("Generating deterministic recommendation...");
    const response = await fetch("/api/user/recommendations/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: "AAPL", event_text: "Operator refresh from recommendations workspace." }),
    });
    if (!response.ok) {
      setStatus(`Generation failed (${response.status})`);
      return;
    }
    await load();
    setStatus("Recommendation refresh completed.");
  }

  return <section style={{ display: "grid", gap: 12 }}>
    <h1>Recommendations</h1>
    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
      <button onClick={generate}>Generate / Refresh recommendations</button>
      <button onClick={() => void load()} disabled={loading}>{loading ? "Refreshing..." : "Reload table"}</button>
      <span style={{ color: "#9fb0c3" }}>{status}</span>
    </div>
    {rows.length === 0 ? <div style={{ border: "1px solid #2a3440", background: "#111922", padding: 12 }}>
      <strong>No recommendation records yet.</strong>
      <div style={{ marginTop: 6, color: "#9fb0c3" }}>Use “Generate / Refresh recommendations” to run deterministic recommendation creation for operator review.</div>
    </div> : null}
    <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 12 }}>
      <table style={{ width: "100%", fontSize: 13 }}><thead><tr><th>symbol</th><th>thesis</th><th>entry</th><th>invalidation</th><th>R/R</th><th>confidence</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id} onClick={() => setSelected(r)} style={{ cursor: "pointer" }}><td>{r.symbol}</td><td>{r.payload?.thesis}</td><td>{r.payload?.entry?.zone_low}/{r.payload?.entry?.zone_high}</td><td>{r.payload?.invalidation?.price}</td><td>{r.payload?.quality?.expected_rr}</td><td>{r.payload?.quality?.confidence}</td></tr>)}</tbody></table>
      <div style={{ border: "1px solid #2a3440", background: "#111922", padding: 12 }}>
        <h3 style={{ marginTop: 0 }}>Actionable detail pane</h3>
        <div><strong>Recommendation ID:</strong> {selected?.recommendation_id ?? "-"}</div>
        <div><strong>Symbol:</strong> {selected?.symbol ?? "-"}</div>
        <div><strong>Catalyst:</strong> {selected?.payload?.catalyst?.type ?? "-"}</div>
        <div><strong>Thesis:</strong> {selected?.payload?.thesis ?? "-"}</div>
        <div><strong>Setup:</strong> {selected?.payload?.entry?.setup_type ?? "-"}</div>
        <div><strong>Entry zone:</strong> {selected?.payload?.entry?.zone_low ?? "-"} - {selected?.payload?.entry?.zone_high ?? "-"}</div>
        <div><strong>Trigger:</strong> {selected?.payload?.entry?.trigger ?? "-"}</div>
        <div><strong>Invalidation:</strong> {selected?.payload?.invalidation?.price ?? "-"} ({selected?.payload?.invalidation?.reason ?? "-"})</div>
        <div><strong>Targets:</strong> T1 {selected?.payload?.targets?.target_1 ?? "-"} / T2 {selected?.payload?.targets?.target_2 ?? "-"}</div>
        <div><strong>Expected R/R:</strong> {selected?.payload?.quality?.expected_rr ?? "-"}</div>
        <div><strong>Confidence:</strong> {selected?.payload?.quality?.confidence ?? "-"}</div>
        <div><strong>Approved:</strong> {String(selected?.payload?.approved ?? "-")}</div>
        <div><strong>No-trade reason:</strong> {selected?.payload?.rejection_reason ?? "n/a"}</div>
        <div><strong>Evidence / provenance:</strong> {(selected?.payload?.evidence?.explanatory_notes ?? []).join(" | ") || "No notes"}</div>
      </div>
    </div>
  </section>;
}
