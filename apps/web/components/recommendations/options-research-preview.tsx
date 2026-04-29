"use client";

import React, { useEffect, useState } from "react";

import { Card, EmptyState, ErrorState, StatusBadge } from "@/components/operator-ui";
import { WorkflowChart } from "@/components/charts/workflow-chart";
import { formatExpectedMoveSummary } from "@/lib/analysis-expected-range";
import type { HacoChartPayload } from "@/lib/haco-api";
import {
  buildOptionsReplayPreviewRequest,
  canRenderOptionsResearchChart,
  fetchOptionsReplayPreview,
  formatOptionsReplayToken,
  formatResearchCell,
  formatResearchCurrency,
  formatResearchValue,
  getExpectedRangeReasonText,
  getOptionsChainUnavailableMessage,
  getOptionsLegDisplayLines,
  getOptionsPremiumLabel,
  getOptionsPremiumValue,
  getOptionsReplayPreviewAvailability,
  getOptionsReplayPreviewBreakevens,
  getOptionsReplayPreviewPayoffRows,
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
        <StatusBadge tone="neutral">Execution disabled</StatusBadge>
        <StatusBadge tone="neutral">Non-persisted</StatusBadge>
        {preview ? <StatusBadge tone={statusTone}>{formatOptionsReplayToken(preview.status)}</StatusBadge> : null}
      </div>

      <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.55, marginBottom: 10 }}>
        Research only. Does not create replay runs, orders, or positions.
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
            Read-only operator preview only. Persisted replay, orders, and paper positions remain unavailable.
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
          {setup.operator_disclaimer ?? "Options research — paper only. Not execution support."} Recommendation queue, persisted replay runs, and paper-order actions remain intentionally unavailable in this Phase 8C slice.
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
