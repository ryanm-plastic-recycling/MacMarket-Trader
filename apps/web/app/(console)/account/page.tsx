"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SignOutButton } from "@clerk/nextjs";

import { Card, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

function safeIdentity(value: string | null | undefined, fallback = "Identity pending"): string {
  if (!value) return fallback;
  const trimmed = value.trim();
  if (trimmed.startsWith("{{") && trimmed.endsWith("}}")) return fallback;
  if (trimmed.includes("invited::")) return fallback;
  return trimmed;
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString();
}

type OnboardingStatus = { has_schedule: boolean; has_replay: boolean; has_order: boolean; has_viewed_haco: boolean | null; completed: number; total: number };

export default function Page() {
  const [user, setUser] = useState<any>(null);
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState("dark");
  useEffect(() => {
    fetchWorkflowApi<any>("/api/user/me").then((r) => {
      if (!r.ok) { setError(r.error ?? "Unable to load account details."); return; }
      setError(null);
      setUser(r.data);
    });
    fetchWorkflowApi<OnboardingStatus>("/api/user/onboarding-status").then((r) => {
      if (r.ok && r.data) {
        const hacoViewed = typeof window !== "undefined" && window.localStorage.getItem("macmarket-haco-visited") === "true";
        setOnboarding({ ...r.data, has_viewed_haco: hacoViewed });
      }
    });
    setTheme(window.localStorage.getItem("macmarket-theme") === "light" ? "light" : "dark");
  }, []);

  return <section style={{ display: "grid", gap: 12 }}>
    <PageHeader title="Account" subtitle="Self-service profile, approval status, and authentication posture for private-alpha desk access." />
    <Card title="What this page is for">
      Confirm your authorization state before running recommendations, replay, or paper orders. If anything is out of date, contact an admin from the invite-only onboarding flow.
    </Card>
    {error ? <ErrorState title="Account unavailable" hint={error} /> : null}
    {user?.identity_warning ? <StatusBadge tone="warn">Identity data incomplete: {user.identity_warning}</StatusBadge> : null}
    {onboarding && (
      <Card title={`Onboarding progress — ${onboarding.completed + (onboarding.has_viewed_haco ? 1 : 0)}/${onboarding.total} complete`}>
        <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", background: "#2a3445", marginBottom: 12 }}>
          <div style={{ flex: onboarding.completed + (onboarding.has_viewed_haco ? 1 : 0), background: "#4caf50", transition: "flex 0.3s" }} />
          <div style={{ flex: onboarding.total - onboarding.completed - (onboarding.has_viewed_haco ? 1 : 0), background: "#2a3445" }} />
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          {[
            { done: onboarding.has_schedule, label: "Create a scheduled strategy report", href: "/schedules" },
            { done: onboarding.has_replay, label: "Run a replay", href: "/replay-runs" },
            { done: onboarding.has_order, label: "Stage a paper order", href: "/orders" },
            { done: !!onboarding.has_viewed_haco, label: "Review HACO context", href: "/haco-context" },
          ].map(({ done, label, href }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <StatusBadge tone={done ? "good" : "neutral"}>{done ? "done" : "pending"}</StatusBadge>
              {done ? <span>{label}</span> : <Link href={href} style={{ color: "#7ec8f7" }}>{label}</Link>}
            </div>
          ))}
        </div>
      </Card>
    )}
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
        <div>Last seen: {formatTimestamp(user?.last_seen_at)}</div>
        <div>Last authenticated: {formatTimestamp(user?.last_authenticated_at)}</div>
        <div>Invite-only onboarding: active</div>
      </Card>
      <Card title="Preferences">
        <div>Theme preference: <StatusBadge tone="neutral">{theme}</StatusBadge></div>
        <div>Theme toggle persists SSR-safe cookie + local storage.</div>
        <SignOutButton><button>Sign out</button></SignOutButton>
      </Card>
    </div>
  </section>;
}
