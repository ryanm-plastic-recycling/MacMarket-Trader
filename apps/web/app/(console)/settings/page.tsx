"use client";

import { useEffect, useState } from "react";

import { Card, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchWorkflowApi } from "@/lib/api-client";

type UserMe = {
  id: number;
  email: string | null;
  display_name: string | null;
  approval_status: string | null;
  app_role: string | null;
  mfa_enabled: boolean | null;
  risk_dollars_per_trade: number | null;
  risk_dollars_per_trade_default: number | null;
};

const RISK_MIN = 1;
const RISK_MAX = 50000;

export default function SettingsPage() {
  const [user, setUser] = useState<UserMe | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [riskInput, setRiskInput] = useState<string>("");
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({
    state: "idle",
    message: "",
  });

  async function loadMe() {
    setFeedback({ state: "loading", message: "Loading account settings…" });
    const r = await fetchWorkflowApi<UserMe>("/api/user/me");
    if (!r.ok) {
      setError(r.error ?? "Unable to load account settings.");
      setFeedback({ state: "error", message: r.error ?? "Unable to load account settings." });
      return;
    }
    setError(null);
    setUser(r.data);
    const effective = r.data?.risk_dollars_per_trade ?? r.data?.risk_dollars_per_trade_default ?? 1000;
    setRiskInput(String(Math.round(Number(effective))));
    setFeedback({ state: "success", message: "Account settings loaded." });
  }

  useEffect(() => {
    void loadMe();
  }, []);

  async function saveRisk() {
    const value = Number(riskInput);
    if (!Number.isFinite(value) || value < RISK_MIN || value > RISK_MAX) {
      setFeedback({ state: "error", message: `Risk per trade must be between $${RISK_MIN} and $${RISK_MAX}.` });
      return;
    }
    setFeedback({ state: "loading", message: "Saving…" });
    const r = await fetchWorkflowApi<{ risk_dollars_per_trade: number | null; risk_dollars_per_trade_default: number | null }>(
      "/api/user/settings",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ risk_dollars_per_trade: value }),
      },
    );
    if (!r.ok) {
      setFeedback({ state: "error", message: r.error ?? "Save failed." });
      return;
    }
    setFeedback({ state: "success", message: "Risk per trade updated." });
    // Refresh /me so the displayed value matches what the backend persisted.
    await loadMe();
  }

  const effectiveRisk = user?.risk_dollars_per_trade ?? user?.risk_dollars_per_trade_default ?? null;
  const usingDefault = user?.risk_dollars_per_trade == null;

  return (
    <section className="op-stack">
      <PageHeader
        title="Settings"
        subtitle="Per-operator preferences. Sizing applies to new recommendations only — open positions are unaffected."
      />
      {error ? <ErrorState title="Settings unavailable" hint={error} /> : null}

      <Card title="Trade sizing">
        <div className="op-row">
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>Risk per trade ($)</span>
            <input
              type="number"
              min={RISK_MIN}
              max={RISK_MAX}
              step={1}
              value={riskInput}
              onChange={(e) => setRiskInput(e.target.value)}
              style={{ width: 140 }}
            />
          </label>
          <button onClick={() => void saveRisk()} disabled={feedback.state === "loading"}>
            {feedback.state === "loading" ? "Saving…" : "Save"}
          </button>
          {effectiveRisk != null ? (
            <span style={{ fontSize: "0.82rem", color: "var(--op-muted, #7a8999)" }}>
              Currently {usingDefault ? "using default" : "override"}: <strong>${Number(effectiveRisk).toFixed(0)}</strong>
            </span>
          ) : null}
        </div>
        <div style={{ marginTop: 8, fontSize: "0.82rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
          Amount risked per paper trade. Applied to all new recommendations. Does not affect existing open positions.
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void loadMe()} />
      </Card>

      <Card title="Account">
        {!user ? (
          <div style={{ color: "var(--op-muted, #7a8999)" }}>Loading account…</div>
        ) : (
          <div className="op-grid-2">
            <div>
              <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Email</div>
              <strong>{user.email ?? "—"}</strong>
            </div>
            <div>
              <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Display name</div>
              <strong>{user.display_name ?? "—"}</strong>
            </div>
            <div>
              <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Role</div>
              <StatusBadge tone="neutral">{user.app_role ?? "—"}</StatusBadge>
            </div>
            <div>
              <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>Approval</div>
              <StatusBadge tone={user.approval_status === "approved" ? "good" : "warn"}>
                {user.approval_status ?? "—"}
              </StatusBadge>
            </div>
            <div>
              <div style={{ fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>MFA</div>
              <StatusBadge tone={user.mfa_enabled ? "good" : "warn"}>
                {user.mfa_enabled ? "enabled" : "not enabled"}
              </StatusBadge>
              {!user.mfa_enabled ? (
                <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
                  MFA is not enabled. Contact admin to enroll. (Self-service enrollment requires Clerk paid plan.)
                </div>
              ) : null}
            </div>
          </div>
        )}
      </Card>
    </section>
  );
}
