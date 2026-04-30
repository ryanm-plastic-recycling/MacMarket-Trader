"use client";

import React, { useEffect, useMemo, useState } from "react";

import { Card, EmptyState, ErrorState, StatusBadge } from "@/components/operator-ui";
import {
  fetchOptionsPaperPositions,
  formatOptionsReplayToken,
  formatResearchCurrency,
  formatResearchTimestamp,
  type OptionsPaperLifecycleSummary,
} from "@/lib/recommendations";

export const OPTIONS_DURABLE_SOURCE_CONTEXT_NOTE =
  "Provider/source/as-of details are captured in research context; durable paper lifecycle rows may not include full provider metadata yet.";
export const OPTIONS_DURABLE_PURPOSE_COPY =
  "These rows come from paper option structures saved in Recommendations. This section is display-only for now; manual close is currently handled from the Recommendations options workflow.";
export const OPTIONS_COMMISSION_REMINDER_COPY =
  "Options commission is per contract per leg, not multiplied by 100.";
export const OPTIONS_COMMISSION_FORMULA_COPY =
  "commission per contract × contracts × legs × events";

function formatCompactCurrency(value: number | null | undefined): string {
  return formatResearchCurrency(value, "—");
}

function formatCompactTimestamp(value: string | null | undefined): string {
  return formatResearchTimestamp(value, "—");
}

function formatCompactCount(value: number | null | undefined, suffix: string): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "Unavailable";
  return `${value} ${suffix}${value === 1 ? "" : "s"}`;
}

function formatCompactNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

function formatLegCount(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "Unavailable";
  return `${value} leg${value === 1 ? "" : "s"}`;
}

function formatSafeText(value: string | null | undefined, fallback = "—"): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed : fallback;
}

function structureTone(status: string): "good" | "warn" | "neutral" {
  const normalized = status.trim().toLowerCase();
  if (normalized === "closed") return "good";
  if (normalized === "open") return "warn";
  return "neutral";
}

function lifecycleStatusLabel(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized === "open") return "Open paper position";
  if (normalized === "closed") return "Manually closed paper position";
  if (normalized.includes("expire") || normalized.includes("settlement")) {
    return "Expired / settlement not supported yet";
  }
  return formatOptionsReplayToken(status);
}

function formatOpeningPremium(item: OptionsPaperLifecycleSummary): string {
  if (item.opening_net_debit != null) return `Debit ${formatCompactCurrency(item.opening_net_debit)}`;
  if (item.opening_net_credit != null) return `Credit ${formatCompactCurrency(item.opening_net_credit)}`;
  return "Opening premium —";
}

function formatBreakevens(values: number[] | null | undefined): string {
  const safeValues = (values ?? []).filter((value) => typeof value === "number" && Number.isFinite(value));
  return safeValues.length > 0 ? safeValues.map((value) => formatCompactCurrency(value)).join(" / ") : "—";
}

function renderPaperRecordFlags(item: OptionsPaperLifecycleSummary) {
  const paperText = item.paper_only ? "Paper-only" : "Paper context unavailable";
  const executionText = item.execution_enabled === false ? "execution_enabled=false" : "Execution flag unavailable";
  return (
    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", marginTop: 2 }}>
      {paperText} · {executionText} · persisted paper record
    </div>
  );
}

function renderLegDetails(item: OptionsPaperLifecycleSummary) {
  const legs = Array.isArray(item.legs) ? item.legs : [];
  if (legs.length === 0) {
    return (
      <details>
        <summary>Legs unavailable</summary>
        <div style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
          Leg detail unavailable.
        </div>
      </details>
    );
  }

  return (
    <details>
      <summary>{formatLegCount(item.leg_count)}</summary>
      <div style={{ marginTop: 6, overflowX: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
        <table className="op-table" style={{ margin: 0 }}>
          <thead>
            <tr>
              <th>action</th>
              <th>right</th>
              <th>strike</th>
              <th>expiry</th>
              <th>contracts</th>
              <th>multiplier</th>
              <th>entry premium</th>
              <th>exit premium</th>
              <th>leg gross</th>
              <th>leg commission</th>
              <th>leg net</th>
            </tr>
          </thead>
          <tbody>
            {legs.map((leg, index) => (
              <tr key={`${item.position_id}-leg-${index}`}>
                <td>
                  {formatSafeText(leg.action)}
                  {leg.label ? (
                    <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>
                      {leg.label}
                    </div>
                  ) : null}
                </td>
                <td>{formatSafeText(leg.right).toUpperCase()}</td>
                <td>{formatCompactNumber(leg.strike)}</td>
                <td>{formatSafeText(leg.expiration)}</td>
                <td>{formatCompactCount(leg.quantity, "contract")}</td>
                <td>{formatCompactNumber(leg.multiplier)}</td>
                <td>{formatCompactCurrency(leg.entry_premium ?? null)}</td>
                <td>{formatCompactCurrency(leg.exit_premium ?? null)}</td>
                <td>{formatCompactCurrency(leg.leg_gross_pnl ?? null)}</td>
                <td>{formatCompactCurrency(leg.leg_commission ?? null)}</td>
                <td>{formatCompactCurrency(leg.leg_net_pnl ?? null)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function PaperOptionsPositionsSectionContent({
  items,
  loading,
  error,
  onRetry,
}: {
  items: OptionsPaperLifecycleSummary[];
  loading: boolean;
  error: string | null;
  onRetry?: (() => void) | undefined;
}) {
  const openItems = useMemo(
    () => items.filter((item) => item.status.trim().toLowerCase() === "open"),
    [items],
  );
  const closedItems = useMemo(
    () => items.filter((item) => item.status.trim().toLowerCase() !== "open"),
    [items],
  );

  return (
    <Card title="Paper options positions">
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
        <StatusBadge tone="neutral">Paper-only</StatusBadge>
        <StatusBadge tone="neutral">Durable paper lifecycle records</StatusBadge>
        <StatusBadge tone="neutral">No broker orders were sent</StatusBadge>
        <StatusBadge tone="neutral">Display-only</StatusBadge>
        <StatusBadge tone="neutral">Source unavailable on durable rows</StatusBadge>
        <StatusBadge tone="neutral">As-of unavailable on durable rows</StatusBadge>
      </div>
      <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.84rem", marginBottom: 10, lineHeight: 1.45 }}>
        {OPTIONS_DURABLE_PURPOSE_COPY} Provider/source context may be limited on durable lifecycle rows.
      </div>
      <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.84rem", marginBottom: 10, lineHeight: 1.45 }}>
        {OPTIONS_DURABLE_SOURCE_CONTEXT_NOTE} Source unavailable / As-of unavailable here is not a lifecycle error.
      </div>
      <details style={{ marginBottom: 10 }}>
        <summary style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.84rem" }}>Options commission reminder</summary>
        <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.84rem", lineHeight: 1.45, marginTop: 4 }}>
          {OPTIONS_COMMISSION_REMINDER_COPY} Formula: {OPTIONS_COMMISSION_FORMULA_COPY}.
        </div>
      </details>
      {loading && items.length === 0 ? (
        <div style={{ color: "var(--op-muted, #7a8999)" }}>Loading paper options positions...</div>
      ) : null}
      {error ? (
        <ErrorState
          title="Failed to load paper options positions"
          hint={error}
        />
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <EmptyState
          title="No paper options positions yet"
          hint="Go to Recommendations in options mode and use Save as paper option position to create a persisted paper-only record you can review here later."
        />
      ) : null}
      {!error && items.length > 0 ? (
        <div className="op-stack" style={{ gap: 12 }}>
          <section>
            <div style={{ marginBottom: 6, fontWeight: 600 }}>Open paper positions</div>
            {openItems.length === 0 ? (
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.9rem" }}>
                No open paper option positions.
              </div>
            ) : (
              <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                <table className="op-table">
                  <thead>
                    <tr>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>structure / status</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>opened / expiry</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>premium / risk</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>commissions</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>legs</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>paper result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openItems.map((item) => (
                      <tr key={`open-${item.position_id}`}>
                        <td>
                          <strong>{formatSafeText(item.underlying_symbol, "Unavailable")}</strong>
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                            Position #{item.position_id}
                          </div>
                        </td>
                        <td>
                          {formatOptionsReplayToken(item.structure_type)}
                          <div style={{ marginTop: 3 }}>
                            <StatusBadge tone={structureTone(item.status)}>{lifecycleStatusLabel(item.status)}</StatusBadge>
                          </div>
                          {renderPaperRecordFlags(item)}
                        </td>
                        <td>
                          <div><strong>Opened:</strong> {formatCompactTimestamp(item.opened_at)}</div>
                          <div><strong>Expiration:</strong> {formatSafeText(item.expiration ?? null)}</div>
                          <div><strong>DTE:</strong> Unavailable</div>
                        </td>
                        <td>
                          <div><strong>Open:</strong> {formatOpeningPremium(item)}</div>
                          <div><strong>Max profit:</strong> {formatCompactCurrency(item.max_profit ?? null)}</div>
                          <div><strong>Max loss:</strong> {formatCompactCurrency(item.max_loss ?? null)}</div>
                          <div><strong>Breakevens:</strong> {formatBreakevens(item.breakevens)}</div>
                        </td>
                        <td>
                          <div><strong>Opening:</strong> {formatCompactCurrency(item.opening_commissions ?? null)}</div>
                          <div><strong>Closing:</strong> —</div>
                          <div><strong>Total:</strong> —</div>
                        </td>
                        <td>{renderLegDetails(item)}</td>
                        <td>
                          <strong>Not final</strong>
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                            Gross, commissions, and net paper result appear after manual close.
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section>
            <div style={{ marginBottom: 6, fontWeight: 600 }}>Manually closed paper positions</div>
            {closedItems.length === 0 ? (
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.9rem" }}>
                No manually closed paper option positions yet.
              </div>
            ) : (
              <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                <table className="op-table">
                  <thead>
                    <tr>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>structure / status</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>opened / closed</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>premium / risk</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>legs</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>paper result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedItems.map((item) => (
                      <tr key={`closed-${item.position_id}`}>
                        <td>
                          <strong>{formatSafeText(item.underlying_symbol, "Unavailable")}</strong>
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                            Position #{item.position_id}{item.trade_id != null ? ` · Trade #${item.trade_id}` : ""}
                          </div>
                        </td>
                        <td>
                          {formatOptionsReplayToken(item.structure_type)}
                          <div style={{ marginTop: 3 }}>
                            <StatusBadge tone={structureTone(item.status)}>{lifecycleStatusLabel(item.status)}</StatusBadge>
                          </div>
                          {renderPaperRecordFlags(item)}
                        </td>
                        <td>
                          <div><strong>Opened:</strong> {formatCompactTimestamp(item.opened_at)}</div>
                          <div><strong>Closed:</strong> {formatCompactTimestamp(item.closed_at ?? null)}</div>
                          <div><strong>Expiration:</strong> {formatSafeText(item.expiration ?? null)}</div>
                          <div><strong>DTE:</strong> Unavailable</div>
                        </td>
                        <td>
                          <div><strong>Open:</strong> {formatOpeningPremium(item)}</div>
                          <div><strong>Max profit:</strong> {formatCompactCurrency(item.max_profit ?? null)}</div>
                          <div><strong>Max loss:</strong> {formatCompactCurrency(item.max_loss ?? null)}</div>
                          <div><strong>Breakevens:</strong> {formatBreakevens(item.breakevens)}</div>
                        </td>
                        <td>{renderLegDetails(item)}</td>
                        <td>
                          <div><strong>Manual close recorded</strong></div>
                          <div><strong>Gross P&amp;L:</strong> {formatCompactCurrency(item.gross_pnl ?? null)}</div>
                          <div><strong>Opening commissions:</strong> {formatCompactCurrency(item.opening_commissions ?? null)}</div>
                          <div><strong>Closing commissions:</strong> {formatCompactCurrency(item.closing_commissions ?? null)}</div>
                          <div><strong>Total commissions:</strong> {formatCompactCurrency(item.total_commissions ?? null)}</div>
                          <div><strong>Net P&amp;L:</strong> {formatCompactCurrency(item.net_pnl ?? null)}</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : null}
      {error && onRetry ? (
        <div style={{ marginTop: 8 }}>
          <button onClick={onRetry}>Retry paper options load</button>
        </div>
      ) : null}
    </Card>
  );
}

export function PaperOptionsPositionsSection({ enabled }: { enabled: boolean }) {
  const [items, setItems] = useState<OptionsPaperLifecycleSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    const result = await fetchOptionsPaperPositions();
    if (!result.ok) {
      setError(result.error ?? "Paper options positions load failed.");
      setLoading(false);
      return;
    }
    setItems(result.items);
    setLoading(false);
  }

  useEffect(() => {
    if (!enabled) return;
    void load();
  }, [enabled]);

  return (
    <PaperOptionsPositionsSectionContent
      items={items}
      loading={loading}
      error={error}
      onRetry={() => void load()}
    />
  );
}
