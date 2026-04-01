"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type DashboardPayload = {
  approval_status: string;
  provider_health: Record<string, string>;
  counts: { recommendations: number; replay_runs: number; orders: number; fills: number };
  quick_links: string[];
};

export default function Page() {
  const [data, setData] = useState<DashboardPayload | null>(null);

  useEffect(() => {
    fetch("/api/user/dashboard", { cache: "no-store" }).then((r) => r.json()).then(setData);
  }, []);

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <h1 style={{ marginBottom: 0 }}>Dashboard</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}>
        <div style={{ border: "1px solid #2a3440", padding: 12 }}>
          <h3>Approval status</h3>
          <div>{data?.approval_status ?? "loading..."}</div>
        </div>
        <div style={{ border: "1px solid #2a3440", padding: 12 }}>
          <h3>Provider health</h3>
          {Object.entries(data?.provider_health ?? {}).map(([k, v]) => <div key={k}>{k}: {v}</div>)}
        </div>
      </div>
      <div style={{ border: "1px solid #2a3440", padding: 12 }}>
        <h3>Recent activity counts</h3>
        <div>Recommendations: {data?.counts.recommendations ?? 0}</div>
        <div>Replay runs: {data?.counts.replay_runs ?? 0}</div>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {(data?.quick_links ?? []).map((path) => <Link key={path} href={path}>{path}</Link>)}
      </div>
    </section>
  );
}
