"use client";

import { useEffect, useState } from "react";

type PendingUser = { id: number; email: string; display_name: string };

export function PendingUsersPanel() {
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultById, setResultById] = useState<Record<number, string>>({});
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteStatus, setInviteStatus] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/admin/users/pending", { cache: "no-store" });
      if (!response.ok) throw new Error(`Failed to load pending users (${response.status})`);
      setUsers((await response.json()) as PendingUser[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pending users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function sendInvite() {
    if (!inviteEmail.trim()) return;
    setInviteStatus("Sending invite...");
    const response = await fetch("/api/admin/invites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: inviteEmail.trim(), display_name: inviteName.trim() || undefined }),
    });
    if (!response.ok) {
      setInviteStatus(`Invite failed (${response.status})`);
      return;
    }
    setInviteStatus("Invite sent. User is in pending local-approval state.");
    setInviteEmail("");
    setInviteName("");
    await load();
  }

  async function act(userId: number, action: "approve" | "reject") {
    const approved = action === "approve";
    if (!window.confirm(`${approved ? "Approve" : "Reject"} user #${userId}?`)) return;
    setResultById((prev) => ({ ...prev, [userId]: "Submitting..." }));
    const response = await fetch(`/api/admin/users/${userId}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: userId, note: `Actioned from admin queue (${action})` }) });
    if (!response.ok) {
      setResultById((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setResultById((prev) => ({ ...prev, [userId]: approved ? "Approved" : "Rejected" }));
    await load();
  }

  if (loading) return <p>Loading pending users…</p>;
  if (error) return <p style={{ color: "#ff8b8b" }}>{error}</p>;

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h1 style={{ marginBottom: 0 }}>Pending admin queue</h1>
      <p style={{ marginTop: 0, color: "#9fb0c3" }}>Approval decisions update local DB approval history and preserve local app role policy.</p>
      <div style={{ border: "1px solid #2a3440", padding: 10, background: "#111922", display: "grid", gap: 8 }}>
        <strong>Private alpha invite</strong>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="email@example.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
          <input placeholder="Display name (optional)" value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
          <button onClick={() => void sendInvite()}>Send invite</button>
        </div>
        <span style={{ color: "#9fb0c3" }}>{inviteStatus}</span>
      </div>
      {users.length === 0 ? <p>No pending users.</p> : <table><thead><tr><th>User</th><th>Email</th><th>Actions</th><th>Status</th></tr></thead><tbody>
        {users.map((user) => <tr key={user.id}><td>{user.display_name || "Unknown"}</td><td>{user.email || "missing"}</td><td style={{ display: "flex", gap: 6 }}><button onClick={() => act(user.id, "approve")}>Approve</button><button onClick={() => act(user.id, "reject")}>Reject</button></td><td>{resultById[user.id] ?? "queued"}</td></tr>)}
      </tbody></table>}
    </section>
  );
}
