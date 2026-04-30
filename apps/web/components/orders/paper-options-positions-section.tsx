"use client";

import React, { useEffect, useMemo, useState } from "react";

import { Card, EmptyState, ErrorState, StatusBadge } from "@/components/operator-ui";
import {
  fetchOptionsPaperPositions,
  formatOptionsReplayToken,
  formatResearchCurrency,
  formatResearchTimestamp,
  type OptionsPaperLifecycleSummary,
  type OptionsPaperLifecycleSummaryLeg,
} from "@/lib/recommendations";

export const OPTIONS_DURABLE_SOURCE_CONTEXT_NOTE =
  "Provider/source context is captured in research preview; durable paper lifecycle rows may not include full provider metadata yet.";

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

function structureTone(status: string): "good" | "warn" | "neutral" {
  const normalized = status.trim().toLowerCase();
  if (normalized === "closed") return "good";
  if (normalized === "open") return "warn";
  return "neutral";
}

function formatLegSummary(leg: OptionsPaperLifecycleSummaryLeg): string {
  const parts = [
    leg.action?.trim().toLowerCase(),
    leg.right?.trim().toUpperCase(),
    typeof leg.strike === "number" && Number.isFinite(leg.strike) ? String(leg.strike) : null,
  ].filter(Boolean);
  const headline = parts.join(" ");
  const premiumBits = [
    `entry ${formatCompactCurrency(leg.entry_premium ?? null)}`,
    leg.exit_premium != null ? `exit ${formatCompactCurrency(leg.exit_premium)}` : null,
  ].filter(Boolean);
  const context = [
    typeof leg.expiration === "string" && leg.expiration.trim() ? leg.expiration.trim() : null,
    formatCompactCount(leg.quantity, "contract"),
    premiumBits.join(" · "),
  ].filter(Boolean);
  const label = typeof leg.label === "string" && leg.label.trim() ? leg.label.trim() : null;
  return [headline || "Unavailable", label, context.join(" · ")].filter(Boolean).join(" — ");
}

function renderLegLines(legs: OptionsPaperLifecycleSummaryLeg[]): string[] {
  if (!Array.isArray(legs) || legs.length === 0) {
    return ["Leg detail unavailable."];
  }
  return legs.map((leg) => formatLegSummary(leg));
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
    <Card title="Paper Options Positions">
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
        <StatusBadge tone="neutral">Paper-only</StatusBadge>
        <StatusBadge tone="neutral">Source unavailable on durable rows</StatusBadge>
        <StatusBadge tone="neutral">As-of unavailable on durable rows</StatusBadge>
        <span style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.9rem" }}>
          Durable saved paper option positions and manual-close results. Separate from equity orders and replay payoff preview.
        </span>
      </div>
      <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.84rem", marginBottom: 10, lineHeight: 1.45 }}>
        {OPTIONS_DURABLE_SOURCE_CONTEXT_NOTE} Source unavailable / As-of unavailable here is not a lifecycle error.
      </div>
      {loading && items.length === 0 ? (
        <div style={{ color: "var(--op-muted, #7a8999)" }}>Loading paper options positions…</div>
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
            <div style={{ marginBottom: 6, fontWeight: 600 }}>Open paper options positions</div>
            {openItems.length === 0 ? (
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.9rem" }}>
                No open paper option positions.
              </div>
            ) : (
              <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                <table className="op-table">
                  <thead>
                    <tr>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>structure</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>status</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>expiry</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>contracts</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>opened</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>leg summary</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>close result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openItems.map((item) => (
                      <tr key={`open-${item.position_id}`}>
                        <td>{item.underlying_symbol}</td>
                        <td>{formatOptionsReplayToken(item.structure_type)}</td>
                        <td><StatusBadge tone={structureTone(item.status)}>{item.status}</StatusBadge></td>
                        <td>{item.expiration ?? "—"}</td>
                        <td>
                          {formatCompactCount(item.contract_count ?? null, "contract")}
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                            {item.leg_count} leg{item.leg_count === 1 ? "" : "s"}
                          </div>
                        </td>
                        <td>{formatCompactTimestamp(item.opened_at)}</td>
                        <td>
                          <details>
                            <summary>{item.leg_count} leg{item.leg_count === 1 ? "" : "s"}</summary>
                            <div style={{ marginTop: 6, display: "grid", gap: 4 }}>
                              {renderLegLines(item.legs).map((line) => (
                                <div key={`${item.position_id}-${line}`} style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                                  {line}
                                </div>
                              ))}
                            </div>
                          </details>
                        </td>
                        <td>
                          <strong>Pending manual paper close</strong>
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
            <div style={{ marginBottom: 6, fontWeight: 600 }}>Closed paper options positions</div>
            {closedItems.length === 0 ? (
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.9rem" }}>
                No manually closed paper option positions yet.
              </div>
            ) : (
              <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 8 }}>
                <table className="op-table">
                  <thead>
                    <tr>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>symbol</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>structure</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>status</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>opened → closed</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>contracts</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>leg summary</th>
                      <th style={{ position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)" }}>paper result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedItems.map((item) => (
                      <tr key={`closed-${item.position_id}`}>
                        <td>{item.underlying_symbol}</td>
                        <td>
                          {formatOptionsReplayToken(item.structure_type)}
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                            Position #{item.position_id}{item.trade_id != null ? ` · Trade #${item.trade_id}` : ""}
                          </div>
                        </td>
                        <td><StatusBadge tone={structureTone(item.status)}>{item.status}</StatusBadge></td>
                        <td>
                          {formatCompactTimestamp(item.opened_at)}
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                            {formatCompactTimestamp(item.closed_at ?? null)}
                          </div>
                        </td>
                        <td>
                          {formatCompactCount(item.contract_count ?? null, "contract")}
                          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
                            {item.leg_count} leg{item.leg_count === 1 ? "" : "s"}
                          </div>
                        </td>
                        <td>
                          <details>
                            <summary>{item.leg_count} leg{item.leg_count === 1 ? "" : "s"}</summary>
                            <div style={{ marginTop: 6, display: "grid", gap: 4 }}>
                              {renderLegLines(item.legs).map((line) => (
                                <div key={`${item.position_id}-${line}`} style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
                                  {line}
                                </div>
                              ))}
                            </div>
                          </details>
                        </td>
                        <td>
                          <div><strong>Gross:</strong> {formatCompactCurrency(item.gross_pnl ?? null)}</div>
                          <div><strong>Open comm:</strong> {formatCompactCurrency(item.opening_commissions ?? null)}</div>
                          <div><strong>Close comm:</strong> {formatCompactCurrency(item.closing_commissions ?? null)}</div>
                          <div><strong>Total comm:</strong> {formatCompactCurrency(item.total_commissions ?? null)}</div>
                          <div><strong>Net paper P&amp;L:</strong> {formatCompactCurrency(item.net_pnl ?? null)}</div>
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
