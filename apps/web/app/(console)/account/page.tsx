"use client";

import { useEffect, useState } from "react";

import { Card, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalized } from "@/lib/api-client";

export default function Page() {
  const [user, setUser] = useState<any>(null);
  useEffect(() => { fetchNormalized<any>("/api/user/me").then((r) => r.ok && setUser(r.data)); }, []);

  return <section style={{ display: "grid", gap: 12 }}>
    <PageHeader title="Account" subtitle="Operator profile and private-alpha access status." />
    <div className="op-grid-2">
      <Card title="Identity">
        <div>Email: {user?.email ?? "-"}</div>
        <div>Display name: {user?.display_name ?? "-"}</div>
        <div>Auth provider: Clerk</div>
      </Card>
      <Card title="Authorization & invite state">
        <div>Role: <StatusBadge tone="neutral">{user?.app_role ?? "-"}</StatusBadge></div>
        <div>Approval status: <StatusBadge tone={user?.approval_status === "approved" ? "good" : "warn"}>{user?.approval_status ?? "-"}</StatusBadge></div>
        <div>MFA enabled: {String(user?.mfa_enabled ?? false)}</div>
        <div>Invite-only onboarding: active</div>
      </Card>
    </div>
  </section>;
}
