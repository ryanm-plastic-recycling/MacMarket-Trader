"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalizedAuthed } from "@/lib/api-client";

type PendingUser = { id: number; email: string; display_name: string };
type Invite = { id: number; email: string; display_name: string; status: string; invited_by: string; created_at: string; invite_token: string };

export function PendingUsersPanel() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultById, setResultById] = useState<Record<number, string>>({});
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteStatus, setInviteStatus] = useState("");
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });

  async function load() {
    if (!isLoaded || !isSignedIn) {
      setFeedback({ state: "loading", message: "Initializing authentication session…" });
      return;
    }
    setLoading(true);
    setError(null);
    setFeedback({ state: "loading", message: "Refreshing admin queue…" });
    const [usersResponse, invitesResponse] = await Promise.all([
      fetchNormalizedAuthed<PendingUser>("/api/admin/users/pending", undefined, getToken),
      fetchNormalizedAuthed<Invite>("/api/admin/invites", undefined, getToken),
    ]);

    if (!usersResponse.ok) {
      setError(usersResponse.error ?? "Failed to load pending users.");
      setFeedback({ state: "error", message: usersResponse.error ?? "Failed to load pending users." });
      setLoading(false);
      return;
    }

    setUsers(usersResponse.items);
    setInvites(invitesResponse.ok ? invitesResponse.items : []);
    setFeedback({ state: "success", message: "Admin queue refreshed." });
    setLoading(false);
  }

  useEffect(() => { void load(); }, [isLoaded, isSignedIn]);

  async function sendInvite() {
    if (!inviteEmail.trim()) return;
    setInviteStatus("Sending invite...");
    setFeedback({ state: "loading", message: "Sending invite…" });
    const response = await fetchNormalizedAuthed("/api/admin/invites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: inviteEmail.trim(), display_name: inviteName.trim() || undefined }),
    }, getToken);
    if (!response.ok) {
      setInviteStatus(response.error ?? `Invite failed (${response.status})`);
      setFeedback({ state: "error", message: response.error ?? `Invite failed (${response.status})` });
      return;
    }
    const token = (response.raw as Record<string, any>)?.invite_token;
    setInviteStatus(`Invite sent. Token: ${token ?? "(hidden)"}`);
    setFeedback({ state: "success", message: "Invite sent." });
    setInviteEmail("");
    setInviteName("");
    await load();
  }

  async function act(userId: number, action: "approve" | "reject") {
    setResultById((prev) => ({ ...prev, [userId]: "Submitting..." }));
    const response = await fetchNormalizedAuthed(`/api/admin/users/${userId}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: userId, note: `Actioned from admin queue (${action})` }) }, getToken);
    if (!response.ok) {
      setResultById((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setResultById((prev) => ({ ...prev, [userId]: action === "approve" ? "Approved" : "Rejected" }));
    await load();
  }

  if (loading) return <p>Loading pending users…</p>;
  if (error) return <ErrorState title="Admin queue unavailable" hint={error} />;

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader title="Admin approvals & invites" subtitle="Invite-only onboarding with local approval gating." />
      <Card title="Send private-alpha invite">
        <div className="op-row">
          <input placeholder="email@example.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
          <input placeholder="Display name (optional)" value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
          <button onClick={() => void sendInvite()}>Send invite</button>
          {inviteStatus ? <StatusBadge tone="neutral">{inviteStatus}</StatusBadge> : null}
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
      </Card>

      <div className="op-grid-2">
        <Card title="Pending users">
          {users.length === 0 ? <EmptyState title="No pending users" hint="Send invite to seed approval queue." /> : <table className="op-table"><thead><tr><th>User</th><th>Email</th><th>Actions</th><th>Status</th></tr></thead><tbody>
            {users.map((user) => <tr key={user.id}><td>{user.display_name || "Unknown"}</td><td>{user.email || "missing"}</td><td className="op-row"><button onClick={() => void act(user.id, "approve")}>Approve</button><button onClick={() => void act(user.id, "reject")}>Reject</button></td><td>{resultById[user.id] ?? "queued"}</td></tr>)}</tbody></table>}
        </Card>
        <Card title="Recent invites">
          {invites.length === 0 ? <EmptyState title="No invites sent" hint="Use invite form above." /> : <table className="op-table"><thead><tr><th>created_at</th><th>email</th><th>status</th><th>invited_by</th></tr></thead><tbody>
            {invites.map((invite) => <tr key={invite.id}><td>{invite.created_at}</td><td>{invite.email}</td><td>{invite.status}</td><td>{invite.invited_by}</td></tr>)}</tbody></table>}
        </Card>
      </div>
    </section>
  );
}
