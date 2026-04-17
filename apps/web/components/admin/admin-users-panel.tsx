"use client";

import { useEffect, useState } from "react";

import { Card, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type AdminUser = {
  id: number;
  display_name: string;
  email: string;
  app_role: string;
  approval_status: string;
  mfa_enabled: boolean;
  invite_status?: string | null;
  last_seen_at?: string | null;
  last_authenticated_at?: string | null;
  external_auth_user_id?: string | null;
  identity_warning?: string | null;
};

function cleanIdentity(value: string | null | undefined, fallback: string): string {
  if (!value) return fallback;
  const trimmed = value.trim();
  if (!trimmed || (trimmed.startsWith("{{") && trimmed.endsWith("}}")) || trimmed.includes("invited::")) {
    return fallback;
  }
  return trimmed;
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function AdminUsersPanel() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actionResult, setActionResult] = useState<Record<number, string>>({});
  const [suspendConfirm, setSuspendConfirm] = useState<Record<number, boolean>>({});
  const [deleteConfirm, setDeleteConfirm] = useState<Record<number, boolean>>({});

  async function load() {
    const [usersResult, meResult] = await Promise.all([
      fetchWorkflowApi<AdminUser>("/api/admin/users"),
      fetchWorkflowApi<{ id: number }>("/api/user/me"),
    ]);
    if (!usersResult.ok) {
      setError(usersResult.error ?? "Unable to load current users");
    } else {
      setError(null);
      setUsers(usersResult.items);
    }
    if (meResult.ok && meResult.data) {
      setCurrentUserId(meResult.data.id);
    }
    setLoading(false);
  }

  useEffect(() => { void load(); }, []);

  async function setRole(userId: number, role: "admin" | "user") {
    setActionResult((prev) => ({ ...prev, [userId]: "Updating…" }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/set-role`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setActionResult((prev) => ({ ...prev, [userId]: `Role → ${role}` }));
    setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, app_role: role } : u));
  }

  async function suspendUser(userId: number) {
    setActionResult((prev) => ({ ...prev, [userId]: "Suspending…" }));
    setSuspendConfirm((prev) => ({ ...prev, [userId]: false }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/suspend`, { method: "POST" });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setActionResult((prev) => ({ ...prev, [userId]: "Suspended" }));
    setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, approval_status: "suspended" } : u));
  }

  async function unsuspendUser(userId: number) {
    setActionResult((prev) => ({ ...prev, [userId]: "Unsuspending…" }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/unsuspend`, { method: "POST" });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setActionResult((prev) => ({ ...prev, [userId]: "Approved" }));
    setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, approval_status: "approved" } : u));
  }

  async function approveUser(userId: number) {
    setActionResult((prev) => ({ ...prev, [userId]: "Approving…" }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, note: "Approved via admin panel" }),
    });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setActionResult((prev) => ({ ...prev, [userId]: "Approved" }));
    setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, approval_status: "approved" } : u));
  }

  async function rejectUser(userId: number) {
    setActionResult((prev) => ({ ...prev, [userId]: "Rejecting…" }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, note: "Rejected via admin panel" }),
    });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setActionResult((prev) => ({ ...prev, [userId]: "Rejected" }));
    setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, approval_status: "rejected" } : u));
  }

  async function forceRelogin(userId: number) {
    setActionResult((prev) => ({ ...prev, [userId]: "Invalidating sessions…" }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}/force-password-reset`, { method: "POST" });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: response.error ?? `Failed (${response.status})` }));
      return;
    }
    setActionResult((prev) => ({ ...prev, [userId]: "Sessions invalidated" }));
  }

  async function deleteUser(userId: number) {
    setActionResult((prev) => ({ ...prev, [userId]: "Deleting…" }));
    setDeleteConfirm((prev) => ({ ...prev, [userId]: false }));
    const response = await fetchWorkflowApi(`/api/admin/users/${userId}`, { method: "DELETE" });
    if (!response.ok) {
      setActionResult((prev) => ({ ...prev, [userId]: `Failed (${response.status})` }));
      return;
    }
    setUsers((prev) => prev.filter((u) => u.id !== userId));
    setExpandedId(null);
  }

  function copyToClipboard(value: string) {
    void navigator.clipboard.writeText(value);
  }

  if (loading) return <p>Loading current users…</p>;
  if (error) return <ErrorState title="Users unavailable" hint={error} />;

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <PageHeader
        title="Admin users"
        subtitle="Local app users are source-of-truth for role and approval state."
      />
      <Card title="Current users">
        {users.length === 0 ? (
          <EmptyState title="No users yet" hint="Invite users from Admin / Invites to populate the private-alpha desk." />
        ) : (
          <table className="op-table">
            <thead>
              <tr>
                <th>display name</th>
                <th>email</th>
                <th>role</th>
                <th>approval</th>
                <th>MFA</th>
                <th>invite</th>
                <th>last seen</th>
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isSelf = user.id === currentUserId;
                const isExpanded = expandedId === user.id;
                const status = user.approval_status;

                return (
                  <>
                    <tr
                      key={user.id}
                      style={{ cursor: "pointer" }}
                      onClick={() => setExpandedId(isExpanded ? null : user.id)}
                    >
                      <td>
                        <span style={{ marginRight: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
                          {isExpanded ? "▾" : "▸"}
                        </span>
                        {cleanIdentity(user.display_name, "Identity pending sync")}
                        {isSelf && <span style={{ marginLeft: 6, fontSize: "0.75rem", color: "var(--op-muted, #7a8999)" }}>(you)</span>}
                      </td>
                      <td>{cleanIdentity(user.email, "Identity pending sync")}</td>
                      <td><StatusBadge tone={user.app_role === "admin" ? "good" : "neutral"}>{user.app_role}</StatusBadge></td>
                      <td><StatusBadge tone={status === "approved" ? "good" : status === "suspended" ? "warn" : "neutral"}>{status}</StatusBadge></td>
                      <td>{user.mfa_enabled ? "enabled" : "—"}</td>
                      <td>{user.invite_status ?? "—"}</td>
                      <td>{formatTimestamp(user.last_seen_at)}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <div className="op-row" style={{ gap: 6 }}>
                          {isSelf ? (
                            <span
                              style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}
                              title="Cannot modify your own account"
                            >
                              —
                            </span>
                          ) : (
                            <>
                              {status === "approved" && (
                                <>
                                  {suspendConfirm[user.id] ? (
                                    <>
                                      <span style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Suspend?</span>
                                      <button style={{ fontSize: "0.8rem" }} onClick={() => void suspendUser(user.id)}>Confirm</button>
                                      <button style={{ fontSize: "0.8rem" }} onClick={() => setSuspendConfirm((prev) => ({ ...prev, [user.id]: false }))}>Cancel</button>
                                    </>
                                  ) : (
                                    <button style={{ fontSize: "0.8rem" }} onClick={() => setSuspendConfirm((prev) => ({ ...prev, [user.id]: true }))}>
                                      Suspend
                                    </button>
                                  )}
                                  {user.app_role === "admin" ? (
                                    <button style={{ fontSize: "0.8rem" }} title="Demote to user" onClick={() => void setRole(user.id, "user")}>Make user</button>
                                  ) : (
                                    <button style={{ fontSize: "0.8rem" }} title="Promote to admin" onClick={() => void setRole(user.id, "admin")}>Make admin</button>
                                  )}
                                </>
                              )}
                              {status === "suspended" && (
                                <button style={{ fontSize: "0.8rem" }} onClick={() => void unsuspendUser(user.id)}>Unsuspend</button>
                              )}
                              {(status === "rejected" || status === "pending") && (
                                <button style={{ fontSize: "0.8rem" }} onClick={() => void approveUser(user.id)}>Approve</button>
                              )}
                              {status === "pending" && (
                                <button style={{ fontSize: "0.8rem" }} onClick={() => void rejectUser(user.id)}>Reject</button>
                              )}
                            </>
                          )}
                          {actionResult[user.id] && (
                            <span style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>{actionResult[user.id]}</span>
                          )}
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${user.id}-detail`} style={{ background: "var(--card-bg-alt, #1a2230)" }}>
                        <td colSpan={8} style={{ padding: "10px 16px" }}>
                          <div style={{ display: "grid", gap: 4, fontSize: "0.85rem" }}>
                            <div><strong>Email:</strong> {cleanIdentity(user.email, "pending sync")}</div>
                            <div><strong>Display name:</strong> {cleanIdentity(user.display_name, "pending sync")}</div>
                            <div><strong>Role:</strong> {user.app_role} &nbsp; <strong>Approval:</strong> {status}</div>
                            <div><strong>Last seen:</strong> {formatTimestamp(user.last_seen_at)} &nbsp; <strong>Last auth:</strong> {formatTimestamp(user.last_authenticated_at)}</div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <strong>Clerk ID:</strong>
                              <span style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>
                                {user.external_auth_user_id ?? "—"}
                              </span>
                              {user.external_auth_user_id && (
                                <button
                                  style={{ fontSize: "0.75rem", padding: "2px 8px" }}
                                  onClick={() => copyToClipboard(user.external_auth_user_id!)}
                                >
                                  Copy user ID
                                </button>
                              )}
                            </div>
                            {!isSelf && (
                              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, paddingTop: 6, borderTop: "1px solid var(--table-border, #2a3447)", flexWrap: "wrap" }}>
                                {(status === "approved" || status === "suspended") && (
                                  <button
                                    style={{ fontSize: "0.8rem" }}
                                    title="Invalidate all active Clerk sessions — forces re-login on next request"
                                    onClick={() => void forceRelogin(user.id)}
                                  >
                                    Force re-login
                                  </button>
                                )}
                                {deleteConfirm[user.id] ? (
                                  <>
                                    <span style={{ fontSize: "0.8rem", color: "#c07070" }}>
                                      Permanently delete {cleanIdentity(user.display_name, user.email)}? This cannot be undone.
                                    </span>
                                    <button style={{ fontSize: "0.8rem", color: "#c07070" }} onClick={() => void deleteUser(user.id)}>Delete</button>
                                    <button style={{ fontSize: "0.8rem" }} onClick={() => setDeleteConfirm((prev) => ({ ...prev, [user.id]: false }))}>Cancel</button>
                                  </>
                                ) : (
                                  <button
                                    style={{ fontSize: "0.8rem" }}
                                    onClick={() => setDeleteConfirm((prev) => ({ ...prev, [user.id]: true }))}
                                  >
                                    Delete
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </section>
  );
}
