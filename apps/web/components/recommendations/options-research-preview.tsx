"use client";

import React, { useEffect, useState } from "react";

import { Card, EmptyState, ErrorState, StatusBadge } from "@/components/operator-ui";
import { WorkflowChart } from "@/components/charts/workflow-chart";
import { formatExpectedMoveSummary } from "@/lib/analysis-expected-range";
import type { HacoChartPayload } from "@/lib/haco-api";
import {
  buildOptionsReplayPreviewRequest,
  canRenderOptionsResearchChart,
  describeOptionsCommissionEstimate,
  fetchOptionsCommissionSettings,
  fetchOptionsPaperClose,
  fetchOptionsPaperOpen,
  fetchOptionsReplayPreview,
  formatOptionsLegLabel,
  formatOptionsReplayToken,
  formatResearchCell,
  formatResearchCurrency,
  formatResearchValue,
  getEffectiveOptionsCommissionPerContract,
  getExpectedRangeReasonText,
  getOptionsChainUnavailableMessage,
  getOptionsLegDisplayLines,
  getOptionsPaperOpenAvailability,
  getOptionsPremiumLabel,
  getOptionsPremiumValue,
  getOptionsReplayPreviewAvailability,
  getOptionsReplayPreviewBreakevens,
  getOptionsReplayPreviewPayoffRows,
  OPTIONS_COMMISSION_EXAMPLE_TEXT,
  OPTIONS_COMMISSION_FORMULA_TEXT,
  OPTIONS_COMMISSION_NOT_PER_SHARE_TEXT,
  estimateOptionsCommissionForEvents,
  estimateOptionsCommissionPerEvent,
  type OptionsPaperCloseResponse,
  type OptionsPaperOpenResponse,
  type OptionsReplayPreviewAvailability,
  type OptionsReplayPreviewResponse,
  type OptionsResearchSetup,
} from "@/lib/recommendations";

function getReplayStatusTone(status: OptionsReplayPreviewResponse["status"] | null): "good" | "warn" | "neutral" {
  if (status === "ready") return "good";
  if (status === "blocked") return "warn";
  return "neutral";
}

function getPreviewNetPremiumLabel(preview: OptionsReplayPreviewResponse | null): string {
  if (!preview) return "Net premium";
  if (typeof preview.net_credit === "number" && Number.isFinite(preview.net_credit)) return "Net credit";
  if (typeof preview.net_debit === "number" && Number.isFinite(preview.net_debit)) return "Net debit";
  return "Net premium";
}

function renderMessageList(values: string[] | null | undefined) {
  const items = (values ?? []).filter((value) => typeof value === "string" && value.trim());
  if (items.length === 0) return <div style={{ color: "var(--op-muted, #7a8999)" }}>—</div>;
  return (
    <div className="op-stack" style={{ marginTop: 6, gap: 4 }}>
      {items.map((item) => (
        <div key={item} style={{ color: "var(--op-muted, #7a8999)" }}>
          {formatOptionsReplayToken(item)}
        </div>
      ))}
    </div>
  );
}

function buildClosePremiumInputs(
  openResult: OptionsPaperOpenResponse | null,
): Record<number, string> {
  if (!openResult) return {};
  return Object.fromEntries(openResult.legs.map((leg) => [leg.id, ""]));
}

function summarizePaperLifecycleLeg(
  leg:
    | OptionsPaperOpenResponse["legs"][number]
    | OptionsPaperCloseResponse["legs"][number],
): string {
  return formatOptionsLegLabel({
    action: leg.action,
    right: leg.right,
    strike: leg.strike,
    label: leg.label ?? null,
  });
}

function parseManualCloseLegs(
  openResult: OptionsPaperOpenResponse | null,
  closeInputs: Record<number, string>,
): { legs: Array<{ position_leg_id: number; exit_premium: number }>; reason: string | null } {
  if (!openResult || openResult.legs.length === 0) {
    return { legs: [], reason: "Open a paper option structure before attempting a manual close." };
  }
  const legs: Array<{ position_leg_id: number; exit_premium: number }> = [];
  for (const leg of openResult.legs) {
    const raw = String(closeInputs[leg.id] ?? "").trim();
    if (!raw) {
      return { legs: [], reason: "Manual close requires an exit premium for every open leg." };
    }
    const exitPremium = Number(raw);
    if (!Number.isFinite(exitPremium) || exitPremium < 0) {
      return { legs: [], reason: "Exit premiums must be non-negative numbers for every open leg." };
    }
    legs.push({
      position_leg_id: leg.id,
      exit_premium: exitPremium,
    });
  }
  return { legs, reason: null };
}

export function OptionsPaperLifecyclePanel({
  setup,
  initialCommissionPerContract = null,
  initialOpenResult = null,
  initialCloseResult = null,
  loadCommissionOnMount = true,
}: {
  setup: OptionsResearchSetup;
  initialCommissionPerContract?: number | null;
  initialOpenResult?: OptionsPaperOpenResponse | null;
  initialCloseResult?: OptionsPaperCloseResponse | null;
  loadCommissionOnMount?: boolean;
}) {
  const [commissionPerContract, setCommissionPerContract] = useState<number | null>(initialCommissionPerContract);
  const [commissionError, setCommissionError] = useState<string | null>(null);
  const [openResult, setOpenResult] = useState<OptionsPaperOpenResponse | null>(initialOpenResult);
  const [openLoading, setOpenLoading] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const [closeResult, setCloseResult] = useState<OptionsPaperCloseResponse | null>(initialCloseResult);
  const [closeLoading, setCloseLoading] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);
  const [closeInputs, setCloseInputs] = useState<Record<number, string>>(buildClosePremiumInputs(initialOpenResult));

  useEffect(() => {
    setOpenResult(initialOpenResult);
    setCloseResult(initialCloseResult);
    setOpenLoading(false);
    setCloseLoading(false);
    setOpenError(null);
    setCloseError(null);
    setCloseInputs(buildClosePremiumInputs(initialOpenResult));
  }, [setup, initialOpenResult, initialCloseResult]);

  useEffect(() => {
    if (!loadCommissionOnMount) return;
    let cancelled = false;
    async function loadCommission() {
      const result = await fetchOptionsCommissionSettings();
      if (cancelled) return;
      if (!result.ok) {
        setCommissionError(result.error ?? "Unable to load options commission settings.");
        return;
      }
      const effectiveCommission = getEffectiveOptionsCommissionPerContract(result.data);
      setCommissionPerContract(effectiveCommission);
      setCommissionError(null);
    }
    void loadCommission();
    return () => {
      cancelled = true;
    };
  }, [loadCommissionOnMount]);

  const openAvailability = getOptionsPaperOpenAvailability(setup);
  const hasActiveInMemoryPosition = openResult !== null && closeResult === null;
  const openDisabledReason = hasActiveInMemoryPosition
    ? "This page only tracks the current in-memory paper option position. Manual close it below before opening another from this research preview."
    : openAvailability.reason;
  const canOpenPaperStructure = !hasActiveInMemoryPosition && openAvailability.request !== null;
  const openingCommissionEstimate = openAvailability.request
    ? estimateOptionsCommissionPerEvent(openAvailability.request.legs, commissionPerContract)
    : null;
  const lifecycleCommissionEstimate = openAvailability.request
    ? estimateOptionsCommissionForEvents(openAvailability.request.legs, commissionPerContract, 2)
    : null;
  const openingCommissionBreakdown = openAvailability.request
    ? describeOptionsCommissionEstimate({
        commissionPerContract,
        legs: openAvailability.request.legs,
        eventCount: 1,
        eventLabel: "open",
      })
    : null;
  const lifecycleCommissionBreakdown = openAvailability.request
    ? describeOptionsCommissionEstimate({
        commissionPerContract,
        legs: openAvailability.request.legs,
        eventCount: 2,
        eventLabel: "open/close",
      })
    : null;
  const closeDraft = parseManualCloseLegs(openResult, closeInputs);
  const closeRequest =
    closeDraft.reason == null
      ? {
          settlement_mode: "manual_close" as const,
          legs: closeDraft.legs,
        }
      : null;

  async function openPaperStructure() {
    const request = openAvailability.request;
    if (!request) return;
    setOpenLoading(true);
    setOpenError(null);
    setCloseResult(null);
    const result = await fetchOptionsPaperOpen(request);
    setOpenLoading(false);
    if (!result.ok || !result.data) {
      setOpenError(result.error ?? "Unable to open paper option structure.");
      return;
    }
    setOpenResult(result.data);
    setCloseInputs(buildClosePremiumInputs(result.data));
    setCloseError(null);
    if (typeof result.data.commission_per_contract === "number" && Number.isFinite(result.data.commission_per_contract)) {
      setCommissionPerContract(result.data.commission_per_contract);
    }
  }

  async function closePaperStructure() {
    if (!openResult || !closeRequest) return;
    setCloseLoading(true);
    setCloseError(null);
    const result = await fetchOptionsPaperClose(openResult.position_id, closeRequest);
    setCloseLoading(false);
    if (!result.ok || !result.data) {
      setCloseError(result.error ?? "Unable to close paper option structure.");
      return;
    }
    setCloseResult(result.data);
    if (typeof result.data.commission_per_contract === "number" && Number.isFinite(result.data.commission_per_contract)) {
      setCommissionPerContract(result.data.commission_per_contract);
    }
  }

  return (
    <Card title="Paper option lifecycle">
      <div className="op-row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <StatusBadge tone="warn">Paper-only options lifecycle</StatusBadge>
        <StatusBadge tone="good">Persisted paper position</StatusBadge>
        <StatusBadge tone="neutral">Separate from replay payoff preview</StatusBadge>
      </div>

      <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55, marginBottom: 12 }}>
        Opening here records a persisted paper position for the current options structure.
        It stays separate from the read-only replay payoff preview above.
      </div>

      <div className="op-grid-2" style={{ gap: 12, marginBottom: 12 }}>
        <div>
          <div><strong>Structure:</strong> {formatResearchValue(setup.option_structure?.type)}</div>
          <div><strong>Expiration:</strong> {formatResearchValue(setup.option_structure?.expiration)}</div>
          <div><strong>DTE:</strong> {formatResearchValue(setup.option_structure?.dte)}</div>
          <div><strong>{getOptionsPremiumLabel(setup.option_structure)}:</strong> {formatResearchCurrency(getOptionsPremiumValue(setup.option_structure))}</div>
          <div><strong>Max profit:</strong> {formatResearchCurrency(setup.option_structure?.max_profit)}</div>
          <div><strong>Max loss:</strong> {formatResearchCurrency(setup.option_structure?.max_loss)}</div>
        </div>
        <div>
          <div><strong>Options commission / contract:</strong> {formatResearchCurrency(commissionPerContract)}</div>
          <div><strong>Estimated opening commission:</strong> {formatResearchCurrency(openingCommissionEstimate)}</div>
          <div><strong>Estimated open + close commission:</strong> {formatResearchCurrency(lifecycleCommissionEstimate)}</div>
          <div><strong>Breakevens:</strong> {(() => {
            const breakevens = openAvailability.request?.breakevens ?? [];
            return breakevens.length > 0 ? breakevens.map((value) => formatResearchCurrency(value)).join(" / ") : "Unavailable";
          })()}</div>
        </div>
      </div>

      <div style={{ marginBottom: 12, padding: "10px 12px", borderRadius: 10, border: "1px solid var(--op-border, #1e2d3d)", background: "rgba(18, 28, 40, 0.35)" }}>
        <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>Commission guardrails</div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>{OPTIONS_COMMISSION_NOT_PER_SHARE_TEXT}</div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>{OPTIONS_COMMISSION_FORMULA_TEXT}</div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>{OPTIONS_COMMISSION_EXAMPLE_TEXT}</div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>
          {openingCommissionBreakdown ?? "Current opening estimate unavailable until the structure and fee inputs are complete."}
        </div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>
          {lifecycleCommissionBreakdown ?? "Full-lifecycle estimate unavailable until the structure and fee inputs are complete."}
        </div>
        {commissionError ? (
          <div style={{ color: "var(--op-warn, #f2a03f)", marginTop: 6 }}>
            {commissionError}
          </div>
        ) : null}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>Lifecycle legs</div>
        <div className="op-stack" style={{ gap: 4 }}>
          {(openAvailability.request?.legs ?? []).map((leg, index) => (
            <div key={`${leg.action}-${leg.right}-${leg.strike}-${index}`} style={{ color: "var(--op-muted, #7a8999)" }}>
              {formatOptionsLegLabel(leg)} | qty {leg.quantity} | multiplier {leg.multiplier} | entry premium {formatResearchCurrency(leg.premium)}
            </div>
          ))}
          {(openAvailability.request?.legs ?? []).length === 0 ? (
            <div style={{ color: "var(--op-muted, #7a8999)" }}>Leg detail Unavailable.</div>
          ) : null}
        </div>
      </div>

      <div className="op-row" style={{ alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <button
          className="op-btn op-btn-primary"
          onClick={() => void openPaperStructure()}
          disabled={!canOpenPaperStructure || openLoading}
          title={!canOpenPaperStructure ? openDisabledReason ?? undefined : undefined}
        >
          {openLoading ? "Opening paper structure..." : "Open paper option structure"}
        </button>
        <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>
          {openDisabledReason ?? "Creates a persisted paper option position. Replay payoff preview above remains read-only and non-persisted."}
        </div>
      </div>

      {openError ? (
        <div style={{ color: "var(--op-warn, #f2a03f)", marginBottom: 10 }}>
          {openError}
        </div>
      ) : null}

      {openResult ? (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
          <div className="op-row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
            <StatusBadge tone={closeResult ? "neutral" : "good"}>
              {closeResult ? "Paper option structure closed" : "Paper option structure open"}
            </StatusBadge>
            <StatusBadge tone="neutral">Position #{openResult.position_id}</StatusBadge>
          </div>

          <div className="op-grid-2" style={{ gap: 12, marginBottom: 12 }}>
            <div>
              <div><strong>Position status:</strong> {formatResearchValue(closeResult?.position_status ?? openResult.position_status)}</div>
              <div><strong>Structure:</strong> {formatResearchValue(openResult.structure_type)}</div>
              <div><strong>Opening net debit:</strong> {formatResearchCurrency(openResult.opening_net_debit)}</div>
              <div><strong>Opening net credit:</strong> {formatResearchCurrency(openResult.opening_net_credit)}</div>
              <div><strong>Opening commissions:</strong> {formatResearchCurrency(closeResult?.opening_commissions ?? openResult.opening_commissions)}</div>
            </div>
            <div>
              <div><strong>Max profit:</strong> {formatResearchCurrency(openResult.max_profit)}</div>
              <div><strong>Max loss:</strong> {formatResearchCurrency(openResult.max_loss)}</div>
              <div>
                <strong>Breakevens:</strong>{" "}
                {(openResult.breakevens ?? []).length > 0
                  ? (openResult.breakevens ?? []).map((value) => formatResearchCurrency(value)).join(" / ")
                  : "Unavailable"}
              </div>
              <div><strong>Commission / contract:</strong> {formatResearchCurrency(closeResult?.commission_per_contract ?? openResult.commission_per_contract ?? commissionPerContract)}</div>
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 4 }}>Persisted paper legs</div>
            <div className="op-stack" style={{ gap: 4 }}>
              {openResult.legs.map((leg) => (
                <div key={leg.id} style={{ color: "var(--op-muted, #7a8999)" }}>
                  {summarizePaperLifecycleLeg(leg)} | qty {leg.quantity} | multiplier {leg.multiplier} | entry premium {formatResearchCurrency(leg.entry_premium)}
                </div>
              ))}
            </div>
          </div>

          {!closeResult ? (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
              <div className="op-row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
                <StatusBadge tone="warn">Manual paper close</StatusBadge>
                <StatusBadge tone="neutral">All legs close together</StatusBadge>
              </div>
              <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55, marginBottom: 10 }}>
                Enter one exit premium for every open leg to create a persisted paper option trade.
                Commission is per contract per leg, not multiplied by 100.
              </div>

              <div className="op-stack" style={{ gap: 10, marginBottom: 10 }}>
                {openResult.legs.map((leg) => (
                  <label key={leg.id} style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: "0.85rem" }}>
                      {summarizePaperLifecycleLeg(leg)} | entry {formatResearchCurrency(leg.entry_premium)}
                    </span>
                    <input
                      type="number"
                      min={0}
                      step={0.01}
                      value={closeInputs[leg.id] ?? ""}
                      onChange={(event) =>
                        setCloseInputs((current) => ({
                          ...current,
                          [leg.id]: event.target.value,
                        }))
                      }
                      placeholder="Exit premium"
                      style={{ maxWidth: 220 }}
                    />
                  </label>
                ))}
              </div>

              <div className="op-row" style={{ alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
                <button
                  className="op-btn op-btn-secondary"
                  onClick={() => void closePaperStructure()}
                  disabled={closeRequest == null || closeLoading}
                  title={closeRequest == null ? closeDraft.reason ?? undefined : undefined}
                >
                  {closeLoading ? "Closing paper structure..." : "Close paper option structure"}
                </button>
                <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>
                  {closeDraft.reason ?? "Manual close only in this pass. Expiration settlement stays deferred."}
                </div>
              </div>

              {closeError ? (
                <div style={{ color: "var(--op-warn, #f2a03f)" }}>
                  {closeError}
                </div>
              ) : null}
            </div>
          ) : (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--op-border, #1e2d3d)" }}>
              <div className="op-row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
                <StatusBadge tone="good">Manual paper close recorded</StatusBadge>
                <StatusBadge tone="neutral">Trade #{closeResult.trade_id}</StatusBadge>
              </div>

              <div className="op-grid-2" style={{ gap: 12, marginBottom: 10 }}>
                <div>
                  <div><strong>Settlement mode:</strong> {formatResearchValue(closeResult.settlement_mode)}</div>
                  <div><strong>Gross P&amp;L:</strong> {formatResearchCurrency(closeResult.gross_pnl)}</div>
                  <div><strong>Net P&amp;L:</strong> {formatResearchCurrency(closeResult.net_pnl)}</div>
                </div>
                <div>
                  <div><strong>Opening commissions:</strong> {formatResearchCurrency(closeResult.opening_commissions)}</div>
                  <div><strong>Closing commissions:</strong> {formatResearchCurrency(closeResult.closing_commissions)}</div>
                  <div><strong>Total commissions:</strong> {formatResearchCurrency(closeResult.total_commissions)}</div>
                </div>
              </div>

              <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55, marginBottom: 10 }}>
                Paper fee modeling only. Commission is per contract per leg, not multiplied by 100.
              </div>

              <table className="op-table">
                <thead>
                  <tr>
                    <th>leg</th>
                    <th>entry</th>
                    <th>exit</th>
                    <th>gross P&amp;L</th>
                    <th>commission</th>
                    <th>net P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {closeResult.legs.map((leg) => (
                    <tr key={leg.id}>
                      <td>{summarizePaperLifecycleLeg(leg)}</td>
                      <td>{formatResearchCurrency(leg.entry_premium, "—")}</td>
                      <td>{formatResearchCurrency(leg.exit_premium, "—")}</td>
                      <td>{formatResearchCurrency(leg.leg_gross_pnl, "—")}</td>
                      <td>{formatResearchCurrency(leg.leg_commission, "—")}</td>
                      <td>{formatResearchCurrency(leg.leg_net_pnl, "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ marginTop: 10, color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>
            This page only tracks the newly opened paper option position in memory.
            Broader Orders dashboard parity remains deferred to a later Phase 8 slice.
          </div>
        </div>
      ) : null}
    </Card>
  );
}

export function OptionsReplayPreviewPanel({
  availability,
  preview,
  loading,
  error,
  onRunPreview,
}: {
  availability: OptionsReplayPreviewAvailability;
  preview: OptionsReplayPreviewResponse | null;
  loading: boolean;
  error: string | null;
  onRunPreview: () => void;
}) {
  const payoffRows = getOptionsReplayPreviewPayoffRows(preview);
  const breakevens = getOptionsReplayPreviewBreakevens(preview);
  const canRunPreview = availability.request !== null;
  const statusTone = getReplayStatusTone(preview?.status ?? null);
  const netPremiumLabel = getPreviewNetPremiumLabel(preview);
  const previewDisclaimer = preview?.operator_disclaimer ?? "Options research only. Paper-only preview. Not execution support.";

  return (
    <Card title="Replay payoff preview">
      <div className="op-row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <StatusBadge tone="warn">Options replay preview — expiration payoff only</StatusBadge>
        <StatusBadge tone="neutral">Read-only boundary</StatusBadge>
        <StatusBadge tone="neutral">Non-persisted</StatusBadge>
        {preview ? <StatusBadge tone={statusTone}>{formatOptionsReplayToken(preview.status)}</StatusBadge> : null}
      </div>

      <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55, marginBottom: 10 }}>
        Research only. This preview stays read-only and non-persisted.
        {canRunPreview
          ? " Uses the current options structure plus read-only debit/credit assumptions from the research contract."
          : ""}
      </div>

      <div className="op-row" style={{ alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <button
          className="op-btn op-btn-secondary"
          onClick={onRunPreview}
          disabled={!canRunPreview || loading}
          title={!canRunPreview ? availability.reason ?? "Replay payoff preview unavailable." : undefined}
        >
          {loading ? "Previewing…" : "Preview expiration payoff"}
        </button>
        {!canRunPreview ? (
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>
            {availability.reason ?? "Replay payoff preview unavailable for this structure."}
          </div>
        ) : (
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>
            Read-only operator preview only. Use the separate paper lifecycle panel below for persisted paper-state actions.
          </div>
        )}
      </div>

      {error ? (
        <div style={{ color: "var(--op-warn, #f2a03f)", marginBottom: 10 }}>
          {error}
        </div>
      ) : null}

      {!preview && !loading && !error && canRunPreview ? (
        <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.88rem", lineHeight: 1.5 }}>
          Run the preview to inspect max profit/loss, breakevens, and a compact expiration payoff table for the current structure.
        </div>
      ) : null}

      {preview ? (
        <>
          <div className="op-grid-2" style={{ gap: 12, marginTop: 4 }}>
            <div>
              <div><strong>Status:</strong> {formatOptionsReplayToken(preview.status)}</div>
              <div><strong>Structure:</strong> {formatOptionsReplayToken(preview.structure_type)}</div>
              <div><strong>{netPremiumLabel}:</strong> {formatResearchCurrency(preview.net_credit ?? preview.net_debit)}</div>
              <div><strong>Max profit:</strong> {formatResearchCurrency(preview.max_profit)}</div>
              <div><strong>Max loss:</strong> {formatResearchCurrency(preview.max_loss)}</div>
              <div>
                <strong>Breakevens:</strong>{" "}
                {breakevens.length > 0
                  ? breakevens.map((value) => formatResearchCurrency(value)).join(" / ")
                  : "Unavailable"}
              </div>
            </div>
            <div>
              <div><strong>Defined risk:</strong> {preview.is_defined_risk ? "Yes" : "No"}</div>
              <div><strong>Execution enabled:</strong> {preview.execution_enabled ? "Yes" : "No"}</div>
              <div><strong>Persistence enabled:</strong> {preview.persistence_enabled ? "Yes" : "No"}</div>
              <div><strong>Preview type:</strong> {formatOptionsReplayToken(preview.preview_type)}</div>
              <div><strong>Blocked reason:</strong> {formatOptionsReplayToken(preview.blocked_reason)}</div>
              <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
                {previewDisclaimer}
              </div>
            </div>
          </div>

          <div className="op-grid-2" style={{ gap: 12, marginTop: 14 }}>
            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Warnings</div>
              {renderMessageList(preview.warnings)}
            </div>
            <div>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Caveats</div>
              {renderMessageList(preview.caveats)}
            </div>
          </div>

          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Expiration payoff table</div>
            {payoffRows.length > 0 ? (
              <table className="op-table">
                <thead>
                  <tr>
                    <th>underlying</th>
                    <th>total payoff</th>
                  </tr>
                </thead>
                <tbody>
                  {payoffRows.map((row) => (
                    <tr key={`${row.underlying_price}-${row.total_payoff}`}>
                      <td>{formatResearchCell(row.underlying_price)}</td>
                      <td>{formatResearchCurrency(row.total_payoff, "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>
                Payoff table Unavailable for the current preview response.
              </div>
            )}
          </div>
        </>
      ) : null}
    </Card>
  );
}

export function OptionsResearchPreview({
  setup,
  loading,
  error,
  chartPayload,
  chartStorageKey,
  chartSourceLabel,
  chartBlockedByFallback,
}: {
  setup: OptionsResearchSetup | null;
  loading: boolean;
  error: string | null;
  chartPayload: HacoChartPayload | null;
  chartStorageKey: string;
  chartSourceLabel: string;
  chartBlockedByFallback: boolean;
}) {
  const [replayPreview, setReplayPreview] = useState<OptionsReplayPreviewResponse | null>(null);
  const [replayPreviewLoading, setReplayPreviewLoading] = useState(false);
  const [replayPreviewError, setReplayPreviewError] = useState<string | null>(null);

  useEffect(() => {
    setReplayPreview(null);
    setReplayPreviewError(null);
    setReplayPreviewLoading(false);
  }, [setup]);

  if (loading && !setup) {
    return <Card title="Options research preview"><EmptyState title="Loading options research" hint="Fetching the same protected setup contract used by Analysis." /></Card>;
  }

  if (error) {
    return <ErrorState title="Options research preview unavailable" hint={error} />;
  }

  if (!setup) {
    return (
      <Card title="Options research preview">
        <EmptyState
          title="No options research contract selected"
          hint="Start from Analysis with an options setup to load a read-only research preview."
        />
      </Card>
    );
  }

  const structure = setup.option_structure ?? null;
  const premiumLabel = getOptionsPremiumLabel(structure);
  const premiumValue = getOptionsPremiumValue(structure);
  const chainPreview = setup.options_chain_preview ?? null;
  const expectedRangeReason = getExpectedRangeReasonText(setup.expected_range);
  const chainUnavailableMessage = getOptionsChainUnavailableMessage(chainPreview);
  const chartCanRender = canRenderOptionsResearchChart({
    marketMode: setup.market_mode,
    requestedSymbol: setup.symbol,
    setupSymbol: setup.symbol,
    workflowSource: chartSourceLabel,
  }) && !chartBlockedByFallback;
  const replayAvailability = getOptionsReplayPreviewAvailability(setup);

  async function runReplayPreview() {
    const request = buildOptionsReplayPreviewRequest(setup);
    if (!request) return;

    setReplayPreviewLoading(true);
    setReplayPreviewError(null);
    setReplayPreview(null);

    const result = await fetchOptionsReplayPreview(request);
    setReplayPreviewLoading(false);
    if (!result.ok || !result.data) {
      setReplayPreviewError(result.error ?? "Unable to load options replay preview.");
      return;
    }
    setReplayPreview(result.data);
  }

  return (
    <>
      <Card title="Options research preview">
        <div className="op-row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          <StatusBadge tone="warn">Options research — paper only</StatusBadge>
          <StatusBadge tone="neutral">No execution support</StatusBadge>
          <StatusBadge tone="neutral">{setup.workflow_source}</StatusBadge>
        </div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55 }}>
          {setup.operator_disclaimer ?? "Options research — paper only. Not execution support."} Recommendation queue and persisted equity replay flows remain intentionally unavailable in options mode. Replay payoff preview below stays read-only, while the paper option lifecycle panel records a separate paper-only position.
        </div>
      </Card>

      <div className="op-grid-2">
        <Card title="Research contract">
          <div><strong>Underlying:</strong> {formatResearchValue(setup.symbol)}</div>
          <div><strong>Strategy:</strong> {formatResearchValue(setup.strategy)}</div>
          <div><strong>Timeframe:</strong> {formatResearchValue(setup.timeframe ?? "1D")}</div>
          <div><strong>Workflow source:</strong> {formatResearchValue(setup.workflow_source)}</div>
          <div><strong>Structure:</strong> {formatResearchValue(structure?.type)}</div>
          <div><strong>Expiration:</strong> {formatResearchValue(structure?.expiration)}</div>
          <div><strong>DTE:</strong> {formatResearchValue(structure?.dte)}</div>
          <div><strong>{premiumLabel}:</strong> {formatResearchValue(premiumValue)}</div>
          <div><strong>Max profit:</strong> {formatResearchValue(structure?.max_profit)}</div>
          <div><strong>Max loss:</strong> {formatResearchValue(structure?.max_loss)}</div>
          <div><strong>Breakeven low:</strong> {formatResearchValue(structure?.breakeven_low)}</div>
          <div><strong>Breakeven high:</strong> {formatResearchValue(structure?.breakeven_high)}</div>
          <div><strong>IV snapshot:</strong> {formatResearchValue(structure?.iv_snapshot)}</div>
          <div style={{ marginTop: 8 }}>
            <strong>Legs:</strong>
            <div className="op-stack" style={{ marginTop: 6, gap: 4 }}>
              {getOptionsLegDisplayLines(structure).map((line, index) => (
                <div key={`${line}-${index}`} style={{ color: "var(--op-muted, #7a8999)" }}>
                  {line}
                </div>
              ))}
            </div>
          </div>
          {structure?.event_blockers && structure.event_blockers.length > 0 ? (
            <div style={{ marginTop: 8 }}>
              <strong>Event blockers:</strong>
              <div className="op-stack" style={{ marginTop: 6, gap: 4 }}>
                {structure.event_blockers.map((item) => (
                  <div key={item} style={{ color: "var(--op-muted, #7a8999)" }}>{item}</div>
                ))}
              </div>
            </div>
          ) : null}
        </Card>

        <Card title="Expected range">
          {setup.expected_range ? (
            <>
              <div><strong>Status:</strong> {formatResearchValue(setup.expected_range.status)}</div>
              <div><strong>Method:</strong> {formatResearchValue(setup.expected_range.method)}</div>
              <div><strong>Move:</strong> {formatResearchValue(setup.expected_range.absolute_move)} ({formatResearchValue(setup.expected_range.lower_bound)} to {formatResearchValue(setup.expected_range.upper_bound)})</div>
              <div><strong>Horizon:</strong> {formatResearchValue(setup.expected_range.horizon_value)} {formatResearchValue(setup.expected_range.horizon_unit, "").trim()}</div>
              {expectedRangeReason ? <div><strong>Reason:</strong> {formatResearchValue(expectedRangeReason)}</div> : null}
              <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
                Expected range is research context only. It does not change expiration payoff math or enable execution.
              </div>
              <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
                {formatExpectedMoveSummary(setup.expected_range)}
              </div>
            </>
          ) : (
            <div style={{ color: "var(--op-muted, #7a8999)" }}>Expected range preview unavailable for this setup.</div>
          )}
        </Card>
      </div>

      <OptionsReplayPreviewPanel
        availability={replayAvailability}
        preview={replayPreview}
        loading={replayPreviewLoading}
        error={replayPreviewError}
        onRunPreview={() => void runReplayPreview()}
      />

      <OptionsPaperLifecyclePanel setup={setup} />

      <Card title="Options chain preview">
        {chainPreview === null || chainPreview.reason ? (
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.88rem", lineHeight: 1.5 }}>
            {chainUnavailableMessage}
          </div>
        ) : (
          <>
            <div style={{ fontSize: "0.85rem", marginBottom: 8 }}>
              <strong>Underlying:</strong> {formatResearchValue(chainPreview.underlying ?? setup.symbol)}
              {chainPreview.expiry ? <> &nbsp; <strong>Nearest expiry:</strong> {formatResearchValue(chainPreview.expiry)}</> : null}
              {chainPreview.source ? <> &nbsp; <span style={{ color: "var(--op-muted, #7a8999)" }}>({formatResearchValue(chainPreview.source)})</span></> : null}
            </div>
            <div className="op-grid-2" style={{ gap: 12 }}>
              <div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Calls</div>
                {chainPreview.calls && chainPreview.calls.length > 0 ? (
                  <table className="op-table">
                    <thead><tr><th>strike</th><th>expiry</th><th>last</th><th>volume</th></tr></thead>
                    <tbody>
                      {chainPreview.calls.map((contract, index) => (
                        <tr key={`call-${index}`}>
                          <td>{formatResearchCell(contract.strike)}</td>
                          <td>{formatResearchCell(contract.expiry)}</td>
                          <td>{formatResearchCell(contract.last_price)}</td>
                          <td>{formatResearchCell(contract.volume)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>No call contracts returned.</div>}
              </div>
              <div>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 4 }}>Puts</div>
                {chainPreview.puts && chainPreview.puts.length > 0 ? (
                  <table className="op-table">
                    <thead><tr><th>strike</th><th>expiry</th><th>last</th><th>volume</th></tr></thead>
                    <tbody>
                      {chainPreview.puts.map((contract, index) => (
                        <tr key={`put-${index}`}>
                          <td>{formatResearchCell(contract.strike)}</td>
                          <td>{formatResearchCell(contract.expiry)}</td>
                          <td>{formatResearchCell(contract.last_price)}</td>
                          <td>{formatResearchCell(contract.volume)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.85rem" }}>No put contracts returned.</div>}
              </div>
            </div>
            <div style={{ marginTop: 6, fontSize: "0.78rem", color: "var(--op-muted, #7a8999)" }}>
              {chainPreview.data_as_of
                ? `Reference data as of ${chainPreview.data_as_of}. Research preview only — no execution support.`
                : "Reference-only options chain preview. Missing values remain Unavailable or — until deeper provider work lands."}
            </div>
          </>
        )}
      </Card>

      <Card title="Underlying chart context">
        <div className="op-row" style={{ marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
          <StatusBadge tone={!chartCanRender ? "warn" : "neutral"}>{chartSourceLabel}</StatusBadge>
          {!chartCanRender ? <StatusBadge tone="warn">Chart suppressed to avoid mixed fallback/provider context</StatusBadge> : null}
        </div>
        {!chartCanRender ? (
          <EmptyState
            title="Chart preview unavailable"
            hint="This options research contract is labeled as fallback-sourced, so the underlying chart is suppressed rather than risk a mismatched provider context."
          />
        ) : (
          <WorkflowChart
            chartPayload={chartPayload}
            storageKey={chartStorageKey}
            overlayLevels={[]}
            emptyTitle="No underlying chart context loaded"
            emptyHint="Underlying chart context is unavailable for this research preview."
            sourceLabel={chartSourceLabel}
          />
        )}
      </Card>
    </>
  );
}
