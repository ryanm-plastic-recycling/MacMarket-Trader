"use client";

import React from "react";
import { useEffect, useState } from "react";

import { Card, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { MetricLabel } from "@/components/ui/metric-help";
import { fetchWorkflowApi } from "@/lib/api-client";
import {
  OPTIONS_COMMISSION_EXAMPLE_TEXT,
  OPTIONS_COMMISSION_FORMULA_TEXT,
  OPTIONS_COMMISSION_NOT_PER_SHARE_TEXT,
} from "@/lib/recommendations";

type UserMe = {
  id: number;
  email: string | null;
  display_name: string | null;
  approval_status: string | null;
  app_role: string | null;
  mfa_enabled: boolean | null;
  risk_dollars_per_trade: number | null;
  risk_dollars_per_trade_default: number | null;
  paper_max_order_notional: number | null;
  paper_max_order_notional_default: number | null;
  commission_per_trade: number | null;
  commission_per_trade_default: number | null;
  commission_per_contract: number | null;
  commission_per_contract_default: number | null;
};

const RISK_MIN = 1;
const RISK_MAX = 50000;
const PAPER_MAX_NOTIONAL_MIN = 1;
const PAPER_MAX_NOTIONAL_MAX = 1000000;
const COMMISSION_PER_TRADE_MIN = 0;
const COMMISSION_PER_TRADE_MAX = 1000;
const COMMISSION_PER_CONTRACT_MIN = 0;
const COMMISSION_PER_CONTRACT_MAX = 100;

export default function SettingsPage() {
  const [user, setUser] = useState<UserMe | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [riskInput, setRiskInput] = useState<string>("");
  const [paperMaxNotionalInput, setPaperMaxNotionalInput] = useState<string>("");
  const [commissionPerTradeInput, setCommissionPerTradeInput] = useState<string>("");
  const [commissionPerContractInput, setCommissionPerContractInput] = useState<string>("");
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
    const effectivePaperMaxNotional = r.data?.paper_max_order_notional ?? r.data?.paper_max_order_notional_default ?? 1000;
    setPaperMaxNotionalInput(String(Math.round(Number(effectivePaperMaxNotional))));
    const effectiveCommissionPerTrade = r.data?.commission_per_trade ?? r.data?.commission_per_trade_default ?? 0;
    setCommissionPerTradeInput(String(Number(effectiveCommissionPerTrade).toFixed(2)));
    const effectiveCommissionPerContract = r.data?.commission_per_contract ?? r.data?.commission_per_contract_default ?? 0.65;
    setCommissionPerContractInput(String(Number(effectiveCommissionPerContract).toFixed(2)));
    setFeedback({ state: "success", message: "Account settings loaded." });
  }

  useEffect(() => {
    void loadMe();
  }, []);

  async function saveTradeSettings() {
    const riskValue = Number(riskInput);
    const paperMaxNotionalValue = Number(paperMaxNotionalInput);
    const commissionPerTradeValue = Number(commissionPerTradeInput);
    const commissionPerContractValue = Number(commissionPerContractInput);
    if (!Number.isFinite(riskValue) || riskValue < RISK_MIN || riskValue > RISK_MAX) {
      setFeedback({ state: "error", message: `Risk budget at stop must be between $${RISK_MIN} and $${RISK_MAX}.` });
      return;
    }
    if (
      !Number.isFinite(paperMaxNotionalValue)
      || paperMaxNotionalValue < PAPER_MAX_NOTIONAL_MIN
      || paperMaxNotionalValue > PAPER_MAX_NOTIONAL_MAX
    ) {
      setFeedback({
        state: "error",
        message: `Max paper order notional must be between $${PAPER_MAX_NOTIONAL_MIN} and $${PAPER_MAX_NOTIONAL_MAX}.`,
      });
      return;
    }
    if (
      !Number.isFinite(commissionPerTradeValue)
      || commissionPerTradeValue < COMMISSION_PER_TRADE_MIN
      || commissionPerTradeValue > COMMISSION_PER_TRADE_MAX
    ) {
      setFeedback({
        state: "error",
        message: `Equity commission per trade must be between $${COMMISSION_PER_TRADE_MIN} and $${COMMISSION_PER_TRADE_MAX}.`,
      });
      return;
    }
    if (
      !Number.isFinite(commissionPerContractValue)
      || commissionPerContractValue < COMMISSION_PER_CONTRACT_MIN
      || commissionPerContractValue > COMMISSION_PER_CONTRACT_MAX
    ) {
      setFeedback({
        state: "error",
        message: `Options commission per contract must be between $${COMMISSION_PER_CONTRACT_MIN} and $${COMMISSION_PER_CONTRACT_MAX}.`,
      });
      return;
    }
    setFeedback({ state: "loading", message: "Saving…" });
    const r = await fetchWorkflowApi<{
      risk_dollars_per_trade: number | null;
      risk_dollars_per_trade_default: number | null;
      paper_max_order_notional: number | null;
      paper_max_order_notional_default: number | null;
      commission_per_trade: number | null;
      commission_per_trade_default: number | null;
      commission_per_contract: number | null;
      commission_per_contract_default: number | null;
    }>(
      "/api/user/settings",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          risk_dollars_per_trade: riskValue,
          paper_max_order_notional: paperMaxNotionalValue,
          commission_per_trade: commissionPerTradeValue,
          commission_per_contract: commissionPerContractValue,
        }),
      },
    );
    if (!r.ok) {
      setFeedback({ state: "error", message: r.error ?? "Save failed." });
      return;
    }
    setFeedback({ state: "success", message: "Trade settings updated." });
    // Refresh /me so the displayed value matches what the backend persisted.
    await loadMe();
  }

  const effectiveRisk = user?.risk_dollars_per_trade ?? user?.risk_dollars_per_trade_default ?? null;
  const usingDefaultRisk = user?.risk_dollars_per_trade == null;
  const effectivePaperMaxNotional = user?.paper_max_order_notional ?? user?.paper_max_order_notional_default ?? null;
  const usingDefaultPaperMaxNotional = user?.paper_max_order_notional == null;
  const effectiveCommissionPerTrade = user?.commission_per_trade ?? user?.commission_per_trade_default ?? null;
  const usingDefaultCommissionPerTrade = user?.commission_per_trade == null;
  const effectiveCommissionPerContract = user?.commission_per_contract ?? user?.commission_per_contract_default ?? null;
  const usingDefaultCommissionPerContract = user?.commission_per_contract == null;

  return (
    <section className="op-stack">
      <PageHeader
        title="Settings"
        subtitle="Per-operator preferences. Sizing applies to new recommendations only — open positions are unaffected."
      />
      {error ? <ErrorState title="Settings unavailable" hint={error} /> : null}

      <Card title="Trade sizing + fees">
        <div className="op-row">
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>Risk budget at stop ($)</span>
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
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>Max paper order notional ($)</span>
            <input
              type="number"
              min={PAPER_MAX_NOTIONAL_MIN}
              max={PAPER_MAX_NOTIONAL_MAX}
              step={1}
              value={paperMaxNotionalInput}
              onChange={(e) => setPaperMaxNotionalInput(e.target.value)}
              style={{ width: 140 }}
            />
          </label>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label htmlFor="equity-commission-per-trade">
              <MetricLabel label="Equity commission / trade ($)" term="equity_commission_per_trade" />
            </label>
            <input
              id="equity-commission-per-trade"
              type="number"
              min={COMMISSION_PER_TRADE_MIN}
              max={COMMISSION_PER_TRADE_MAX}
              step={0.01}
              value={commissionPerTradeInput}
              onChange={(e) => setCommissionPerTradeInput(e.target.value)}
              style={{ width: 140 }}
            />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label htmlFor="options-commission-per-contract">
              <MetricLabel label="Options commission per contract ($)" term="options_commission_per_contract" />
            </label>
            <input
              id="options-commission-per-contract"
              type="number"
              min={COMMISSION_PER_CONTRACT_MIN}
              max={COMMISSION_PER_CONTRACT_MAX}
              step={0.01}
              value={commissionPerContractInput}
              onChange={(e) => setCommissionPerContractInput(e.target.value)}
              style={{ width: 140 }}
            />
          </div>
          <button onClick={() => void saveTradeSettings()} disabled={feedback.state === "loading"}>
            {feedback.state === "loading" ? "Saving…" : "Save"}
          </button>
        </div>
        <div style={{ marginTop: 8, fontSize: "0.82rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
          Risk budget at stop is the max loss at invalidation used for recommendation sizing, not a generic trade amount. Max paper order notional caps equity paper staging so demo fills do not silently become oversized positions.
        </div>
        <div style={{ marginTop: 10, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--op-border, #1e2d3d)", background: "rgba(18, 28, 40, 0.35)" }}>
          <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>Options commission guardrails</div>
          <div style={{ fontSize: "0.82rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
            {OPTIONS_COMMISSION_NOT_PER_SHARE_TEXT}
          </div>
          <div style={{ fontSize: "0.82rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
            {OPTIONS_COMMISSION_FORMULA_TEXT}
          </div>
          <div style={{ fontSize: "0.82rem", color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
            {OPTIONS_COMMISSION_EXAMPLE_TEXT}
          </div>
        </div>
        <div style={{ marginTop: 10, display: "grid", gap: 4, fontSize: "0.82rem", color: "var(--op-muted, #7a8999)" }}>
          {effectiveRisk != null ? (
            <div>
              Risk budget at stop: {usingDefaultRisk ? "default" : "override"} <strong>${Number(effectiveRisk).toFixed(0)}</strong>
            </div>
          ) : null}
          {effectivePaperMaxNotional != null ? (
            <div>
              Max paper order notional: {usingDefaultPaperMaxNotional ? "default" : "override"} <strong>${Number(effectivePaperMaxNotional).toFixed(0)}</strong>
            </div>
          ) : null}
          {effectiveCommissionPerTrade != null ? (
            <div>
              Equity commission / trade: {usingDefaultCommissionPerTrade ? "default" : "override"} <strong>${Number(effectiveCommissionPerTrade).toFixed(2)}</strong>
            </div>
          ) : null}
          {effectiveCommissionPerContract != null ? (
            <div>
              Options commission per contract: {usingDefaultCommissionPerContract ? "default" : "override"} <strong>${Number(effectiveCommissionPerContract).toFixed(2)}</strong>
            </div>
          ) : null}
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
