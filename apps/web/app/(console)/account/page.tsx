"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";

import { Card, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalizedAuthed } from "@/lib/api-client";

function safeIdentity(value: string | null | undefined, fallback = "Identity pending"): string {
  if (!value) return fallback;
  const trimmed = value.trim();
  if (trimmed.startsWith("{{") && trimmed.endsWith("}}")) return fallback;
  return trimmed;
}

export default function Page() {
  const { getToken } = useAuth();
  const [user, setUser] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetchNormalizedAuthed<any>("/api/user/me", undefined, getToken).then((r) => {
      if (!r.ok) {
        setError(r.error ?? "Unable to load account details.");
        return;
      }
      setUser(r.data);
    });
  }, []);

  return <section style={{ display: "grid", gap: 12 }}>
    <PageHeader title="Account" subtitle="Self-service profile, approval status, and authentication posture for private-alpha desk access." />
    <Card title="What this page is for">
      Confirm your authorization state before running recommendations, replay, or paper orders. If anything is out of date, contact an admin from the invite-only onboarding flow.
    </Card>
    {error ? <ErrorState title="Account unavailable" hint={error} /> : null}
    {user?.identity_warning ? <StatusBadge tone="warn">Identity data incomplete: {user.identity_warning}</StatusBadge> : null}
    <div className="op-grid-2">
      <Card title="Identity">
        <div>Email: {safeIdentity(user?.email)}</div>
        <div>Display name: {safeIdentity(user?.display_name, "Unnamed user")}</div>
        <div>Auth provider: {user?.auth_provider ?? "clerk"}</div>
      </Card>
      <Card title="Authorization & invite state">
        <div>Role: <StatusBadge tone="neutral">{user?.app_role ?? "-"}</StatusBadge></div>
        <div>Approval status: <StatusBadge tone={user?.approval_status === "approved" ? "good" : "warn"}>{user?.approval_status ?? "-"}</StatusBadge></div>
        <div>MFA enabled: {String(user?.mfa_enabled ?? false)}</div>
        <div>Last seen: {user?.last_seen_at ?? "-"}</div>
        <div>Last authenticated: {user?.last_authenticated_at ?? "-"}</div>
        <div>Invite-only onboarding: active</div>
      </Card>
      <Card title="Preferences">
        <div>Theme preference is available from the top bar and persists locally in this browser.</div>
      </Card>
    </div>
  </section>;
}
