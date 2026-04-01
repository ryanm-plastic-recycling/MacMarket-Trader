"use client";

type PendingUser = { id: number; email: string; display_name: string };

import { useEffect, useState } from "react";

export function PendingUsersPanel() {
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultById, setResultById] = useState<Record<number, string>>({});

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/admin/users/pending", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Failed to load pending users (${response.status})`);
      }
      setUsers((await response.json()) as PendingUser[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pending users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function act(userId: number, action: "approve" | "reject") {
    setResultById((prev) => ({ ...prev, [userId]: "Saving..." }));
    const response = await fetch(`/api/admin/users/${userId}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, note: `Actioned from admin queue (${action})` }),
    });
    if (!response.ok) {
      setResultById((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setResultById((prev) => ({ ...prev, [userId]: action === "approve" ? "Approved" : "Rejected" }));
    await load();
  }

  if (loading) {
    return <p>Loading pending users…</p>;
  }

  if (error) {
    return <p style={{ color: "#ff8b8b" }}>{error}</p>;
  }

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h1 style={{ marginBottom: 0 }}>Pending user approvals</h1>
      <p style={{ marginTop: 0, color: "#9fb0c3" }}>Approve or reject users before they can access the operator console.</p>
      {users.length === 0 ? <p>No pending users.</p> : null}
      {users.map((user) => (
        <article key={user.id} style={{ border: "1px solid #2b3642", background: "#111922", padding: 12 }}>
          <div><strong>{user.display_name || "Unknown"}</strong> ({user.email})</div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={() => act(user.id, "approve")}>Approve</button>
            <button onClick={() => act(user.id, "reject")}>Reject</button>
            <span style={{ color: "#9fb0c3" }}>{resultById[user.id] ?? ""}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
