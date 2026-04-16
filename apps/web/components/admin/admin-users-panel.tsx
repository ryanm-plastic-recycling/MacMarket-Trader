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
  // Per-user action feedback
  const [actionResult, setActionResult] = useState<Record<number, string>>({});
  const [suspendConfirm, setSuspendConfirm] = useState<Record<number, boolean>>({});

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
                      <td><StatusBadge tone={user.approval_status === "approved" ? "good" : user.approval_status === "suspended" ? "warn" : "neutral"}>{user.approval_status}</StatusBadge></td>
                      <td>{user.mfa_enabled ? "enabled" : "—"}</td>
                      <td>{user.invite_status ?? "—"}</td>
                      <td>{formatTimestamp(user.last_seen_at)}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <div className="op-row" style={{ gap: 6 }}>
                          {/* Role toggle */}
                          {!isSelf && (
                            user.app_role === "admin" ? (
                              <button
                                style={{ fontSize: "0.8rem" }}
                                onClick={() => void setRole(user.id, "user")}
                                title="Demote to user"
                              >
                                Make user
                              </button>
                            ) : (
                              <button
                                style={{ fontSize: "0.8rem" }}
                                onClick={() => void setRole(user.id, "admin")}
                                title="Promote to admin"
                              >
                                Make admin
                              </button>
                            )
                          )}
                          {/* Suspend */}
                          {!isSelf && user.approval_status !== "suspended" && (
                            suspendConfirm[user.id] ? (
                              <>
                                <span style={{ fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>Suspend?</span>
                                <button style={{ fontSize: "0.8rem" }} onClick={() => void suspendUser(user.id)}>Confirm</button>
                                <button style={{ fontSize: "0.8rem" }} onClick={() => setSuspendConfirm((prev) => ({ ...prev, [user.id]: false }))}>Cancel</button>
                              </>
                            ) : (
                              <button
                                style={{ fontSize: "0.8rem" }}
                                onClick={() => setSuspendConfirm((prev) => ({ ...prev, [user.id]: true }))}
                              >
                                Suspend
                              </button>
                            )
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
                            <div><strong>Role:</strong> {user.app_role} &nbsp; <strong>Approval:</strong> {user.approval_status}</div>
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
