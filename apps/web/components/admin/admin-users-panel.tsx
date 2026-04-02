"use client";

import { useEffect, useState } from "react";

import { Card, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalized } from "@/lib/api-client";

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

export function AdminUsersPanel() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchNormalized<AdminUser>("/api/admin/users").then((result) => {
      if (!result.ok) {
        setError(result.error ?? "Unable to load current users");
      } else {
        setUsers(result.items);
      }
      setLoading(false);
    });
  }, []);

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
                <th>last seen</th><th>last auth</th><th>external auth id</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.display_name || "-"}</td>
                  <td>{user.email}</td>
                  <td><StatusBadge tone="neutral">{user.app_role}</StatusBadge></td>
                  <td><StatusBadge tone={user.approval_status === "approved" ? "good" : "warn"}>{user.approval_status}</StatusBadge></td>
                  <td>{user.mfa_enabled ? "enabled" : "not enabled"}</td>
                  <td>{user.invite_status ?? "-"}</td>
                  <td>{user.last_seen_at ?? "-"}</td><td>{user.last_authenticated_at ?? "-"}</td><td>{user.external_auth_user_id ?? "-"}{user.identity_warning ? ` (${user.identity_warning})` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </section>
  );
}
