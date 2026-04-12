"use client";

import { useEffect, useRef, useState } from "react";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type PendingUser = { id: number; email: string; display_name: string };
type Invite = { id: number; email: string; display_name: string; status: string; invited_by: string; created_at: string; invite_token: string };
type UserRow = { id: number; email: string; display_name: string; approval_status: string; last_seen_at: string | null };

export function PendingUsersPanel() {
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [recentActivity, setRecentActivity] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultById, setResultById] = useState<Record<number, string>>({});
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteStatus, setInviteStatus] = useState("");
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const inviteEmailRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    setError(null);
    setFeedback({ state: "loading", message: "Refreshing admin queue…" });
    const [usersResponse, invitesResponse, allUsersResponse] = await Promise.all([
      fetchWorkflowApi<PendingUser>("/api/admin/users/pending"),
      fetchWorkflowApi<Invite>("/api/admin/invites"),
      fetchWorkflowApi<UserRow>("/api/admin/users"),
    ]);

    if (!usersResponse.ok) {
      setError(usersResponse.error ?? "Failed to load pending users.");
      setFeedback({ state: "error", message: usersResponse.error ?? "Failed to load pending users." });
      setLoading(false);
      return;
    }

    setUsers(usersResponse.items);
    setInvites(invitesResponse.ok ? invitesResponse.items : []);
    if (allUsersResponse.ok) {
      const nonPending = allUsersResponse.items
        .filter((u) => u.approval_status !== "pending")
        .slice(-3)
        .reverse();
      setRecentActivity(nonPending);
    }
    setFeedback({ state: "success", message: "Admin queue refreshed." });
    setLoading(false);
  }

  useEffect(() => { void load(); }, []);

  async function sendInvite() {
    if (!inviteEmail.trim()) return;
    setInviteStatus("Sending invite...");
    setFeedback({ state: "loading", message: "Sending invite…" });
    const response = await fetchWorkflowApi("/api/admin/invites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: inviteEmail.trim(), display_name: inviteName.trim() || undefined }),
    });
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
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: userId, note: `Actioned from admin queue (${action})` }) });
    if (!response.ok) {
      setResultById((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setResultById((prev) => ({ ...prev, [userId]: action === "approve" ? "Approved" : "Rejected" }));
    await load();
  }

  if (loading) return <p>Loading pending users…</p>;
  if (error) return <ErrorState title="Admin queue unavailable" hint={error} />;

  const activityTone = (status: string): "good" | "warn" | "neutral" =>
    status === "approved" ? "good" : status === "rejected" ? "warn" : "neutral";

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader
        title="Admin approvals & invites"
        subtitle="Invite-only onboarding with local approval gating."
        actions={users.length > 0 ? <StatusBadge tone="warn">{users.length} action{users.length > 1 ? "s" : ""} required</StatusBadge> : null}
      />
      <Card title="Send private-alpha invite">
        <div className="op-row">
          <input ref={inviteEmailRef} placeholder="email@example.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
          <input placeholder="Display name (optional)" value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
          <button onClick={() => void sendInvite()}>Send invite</button>
          {inviteStatus ? <StatusBadge tone="neutral">{inviteStatus}</StatusBadge> : null}
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
      </Card>

      <div className="op-grid-2">
        <Card title="Pending users">
          {users.length === 0
            ? <><EmptyState title="No pending users" hint="Queue is clear. Send an invite to onboard the next alpha user — they'll appear here once they sign up." /><button style={{ marginTop: 8 }} onClick={() => inviteEmailRef.current?.focus()}>Send an invite</button></>

            : <>
                <div style={{ marginBottom: 8 }}><StatusBadge tone="warn">Next action: review and approve or reject each user below</StatusBadge></div>
                <table className="op-table"><thead><tr><th>User</th><th>Email</th><th>Actions</th><th>Status</th></tr></thead><tbody>
                  {users.map((user) => <tr key={user.id}><td>{user.display_name || "Unknown"}</td><td>{user.email || "missing"}</td><td className="op-row"><button onClick={() => void act(user.id, "approve")}>Approve</button><button onClick={() => void act(user.id, "reject")}>Reject</button></td><td>{resultById[user.id] ?? "queued"}</td></tr>)}
                </tbody></table>
              </>}
        </Card>
        <Card title="Recent invites">
          {invites.length === 0 ? <EmptyState title="No invites sent" hint="Use invite form above." /> : <table className="op-table"><thead><tr><th>created_at</th><th>email</th><th>status</th><th>invited_by</th></tr></thead><tbody>
            {invites.map((invite) => <tr key={invite.id}><td>{invite.created_at}</td><td>{invite.email}</td><td>{invite.status}</td><td>{invite.invited_by}</td></tr>)}</tbody></table>}
        </Card>
      </div>

      {recentActivity.length > 0 && (
        <Card title="Recent activity">
          <table className="op-table"><thead><tr><th>User</th><th>Email</th><th>Decision</th><th>Last seen</th></tr></thead><tbody>
            {recentActivity.map((u) => <tr key={u.id}>
              <td>{u.display_name || "Unknown"}</td>
              <td>{u.email}</td>
              <td><StatusBadge tone={activityTone(u.approval_status)}>{u.approval_status}</StatusBadge></td>
              <td>{u.last_seen_at ? new Date(u.last_seen_at).toLocaleDateString() : "—"}</td>
            </tr>)}
          </tbody></table>
        </Card>
      )}
    </section>
  );
}
