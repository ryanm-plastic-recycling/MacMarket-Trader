"use client";

import React from "react";

import type { OptionsExpectedRange } from "@/lib/recommendations";

type ExpectedRangeVisualizationProps = {
  expectedRange?: OptionsExpectedRange | null;
  breakevens?: Array<number | null | undefined> | null;
  currentPrice?: number | null;
  referencePrice?: number | null;
  expiration?: string | null;
  dte?: number | null;
  maxProfit?: number | null;
  maxLoss?: number | null;
  workflowSource?: string | null;
};

type Marker = {
  key: string;
  label: string;
  value: number;
  tone: "reference" | "breakeven";
};

const DISCLAIMER_COPY =
  "Expected Range is research context only. It does not change payoff math or approve execution.";

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function safeText(value: unknown, fallback = "Unavailable"): string {
  if (value == null) return fallback;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return fallback;
    return value.toLocaleString("en-US", {
      minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
      maximumFractionDigits: 2,
    });
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : fallback;
  }
  return fallback;
}

function formatCurrency(value: unknown, fallback = "Unavailable"): string {
  const numeric = finiteNumber(value);
  if (numeric == null) return fallback;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
}

function formatTimestamp(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "As-of unavailable";
  const parsed = new Date(value.trim());
  if (Number.isNaN(parsed.getTime())) return value.trim();
  return `${parsed.toISOString().replace("T", " ").slice(0, 16)} UTC`;
}

function formatToken(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "Unavailable";
  return value
    .trim()
    .split(/[_-]+/)
    .map((part) => {
      const normalized = part.trim().toLowerCase();
      if (!normalized) return "";
      if (normalized === "iv") return "IV";
      if (normalized === "dte") return "DTE";
      return normalized.charAt(0).toUpperCase() + normalized.slice(1);
    })
    .filter(Boolean)
    .join(" ");
}

function deriveReferencePrice(
  lower: number,
  upper: number,
  absoluteMove: number | null,
): number | null {
  if (absoluteMove == null || absoluteMove <= 0) return null;
  return (lower + upper) / 2;
}

function markerPercent(value: number, min: number, max: number): number {
  if (max <= min) return 50;
  return Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
}

function buildDomain(values: number[]): { min: number; max: number } {
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  if (minValue === maxValue) {
    const pad = Math.max(Math.abs(minValue) * 0.02, 1);
    return { min: minValue - pad, max: maxValue + pad };
  }
  const pad = Math.max((maxValue - minValue) * 0.08, 0.01);
  return { min: minValue - pad, max: maxValue + pad };
}

function unavailableReason(expectedRange: OptionsExpectedRange | null | undefined): string {
  if (!expectedRange) return "Expected Range unavailable.";
  if (typeof expectedRange.reason === "string" && expectedRange.reason.trim()) return expectedRange.reason.trim();
  return `${formatToken(expectedRange.status)} expected range.`;
}

export function ExpectedRangeVisualization({
  expectedRange,
  breakevens,
  currentPrice,
  referencePrice,
  expiration,
  dte,
  maxProfit,
  maxLoss,
  workflowSource,
}: ExpectedRangeVisualizationProps) {
  const lowerRaw = finiteNumber(expectedRange?.lower_bound);
  const upperRaw = finiteNumber(expectedRange?.upper_bound);
  const computedRange =
    expectedRange?.status === "computed" && lowerRaw != null && upperRaw != null && lowerRaw !== upperRaw;

  if (!computedRange) {
    return (
      <section
        aria-label="Expected Range visualization"
        style={{
          marginBottom: 12,
          padding: "10px 12px",
          borderRadius: 10,
          border: "1px solid var(--op-border, #1e2d3d)",
          background: "rgba(18, 28, 40, 0.22)",
        }}
      >
        <div style={{ fontSize: "0.82rem", fontWeight: 700, marginBottom: 4 }}>Expected Range visualization</div>
        <div style={{ color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
          Unavailable. {unavailableReason(expectedRange)}
        </div>
        <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5 }}>
          {DISCLAIMER_COPY}
        </div>
      </section>
    );
  }

  const lower = Math.min(lowerRaw, upperRaw);
  const upper = Math.max(lowerRaw, upperRaw);
  const absoluteMove = finiteNumber(expectedRange?.absolute_move);
  const derivedReference = finiteNumber(referencePrice)
    ?? finiteNumber(currentPrice)
    ?? deriveReferencePrice(lower, upper, absoluteMove);
  const breakevenValues = (breakevens ?? []).filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  const markers: Marker[] = [
    ...(derivedReference == null
      ? []
      : [{ key: "reference", label: "Reference", value: derivedReference, tone: "reference" as const }]),
    ...breakevenValues.map((value, index) => ({
      key: `breakeven-${index}-${value}`,
      label: `Breakeven ${index + 1}`,
      value,
      tone: "breakeven" as const,
    })),
  ];
  const domain = buildDomain([lower, upper, ...markers.map((marker) => marker.value)]);
  const lowerPercent = markerPercent(lower, domain.min, domain.max);
  const upperPercent = markerPercent(upper, domain.min, domain.max);
  const rangeLeft = Math.min(lowerPercent, upperPercent);
  const rangeWidth = Math.max(0, Math.abs(upperPercent - lowerPercent));
  const outsideBreakevens = breakevenValues.filter((value) => value < lower || value > upper);

  return (
    <section
      aria-label="Expected Range visualization"
      style={{
        marginBottom: 12,
        padding: "10px 12px",
        borderRadius: 10,
        border: "1px solid var(--op-border, #1e2d3d)",
        background: "rgba(18, 28, 40, 0.22)",
      }}
    >
      <div className="op-row" style={{ justifyContent: "space-between", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: "0.82rem", fontWeight: 700 }}>Expected Range visualization</div>
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem", marginTop: 2 }}>
            {safeText(workflowSource, "Source unavailable")} - {formatToken(expectedRange.method)} -{" "}
            {formatTimestamp(expectedRange.snapshot_timestamp)}
          </div>
        </div>
        <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>
          Expiration {safeText(expiration)} - DTE {safeText(dte, "-")}
        </div>
      </div>

      <div style={{ position: "relative", height: 64, margin: "8px 4px 6px" }}>
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 26,
            height: 10,
            borderRadius: 999,
            background: "rgba(122, 137, 153, 0.22)",
          }}
        />
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            left: `${rangeLeft}%`,
            width: `${rangeWidth}%`,
            top: 24,
            height: 14,
            borderRadius: 999,
            background: "rgba(66, 184, 131, 0.45)",
            border: "1px solid rgba(66, 184, 131, 0.62)",
          }}
        />
        {[
          { key: "lower", label: "Lower", value: lower, tone: "range" as const },
          { key: "upper", label: "Upper", value: upper, tone: "range" as const },
          ...markers,
        ].map((marker) => {
          const left = markerPercent(marker.value, domain.min, domain.max);
          const color =
            marker.tone === "breakeven"
              ? "var(--op-warn, #f2a03f)"
              : marker.tone === "reference"
                ? "var(--op-accent, #5ab0ff)"
                : "var(--op-good, #42b883)";
          return (
            <div
              key={marker.key}
              style={{
                position: "absolute",
                left: `${left}%`,
                top: marker.tone === "breakeven" ? 13 : 8,
                transform: "translateX(-50%)",
                width: marker.tone === "breakeven" ? 2 : 3,
                height: marker.tone === "breakeven" ? 34 : 44,
                borderRadius: 999,
                background: color,
              }}
              title={`${marker.label}: ${formatCurrency(marker.value)}`}
            >
              <span
                style={{
                  position: "absolute",
                  top: marker.tone === "breakeven" ? 36 : 46,
                  left: "50%",
                  transform: "translateX(-50%)",
                  whiteSpace: "nowrap",
                  color: "var(--op-muted, #7a8999)",
                  fontSize: "0.68rem",
                  fontWeight: 600,
                }}
              >
                {marker.label}
              </span>
            </div>
          );
        })}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(135px, 1fr))",
          gap: 8,
          marginTop: 16,
          fontSize: "0.8rem",
        }}
      >
        <div><strong>Lower:</strong> {formatCurrency(lower)}</div>
        <div><strong>Upper:</strong> {formatCurrency(upper)}</div>
        <div><strong>Reference:</strong> {derivedReference == null ? "Unavailable" : formatCurrency(derivedReference)}</div>
        <div><strong>Breakevens:</strong> {breakevenValues.length > 0 ? breakevenValues.map((value) => formatCurrency(value)).join(" / ") : "Unavailable"}</div>
        <div><strong>Max profit:</strong> {formatCurrency(maxProfit)}</div>
        <div><strong>Max loss:</strong> {formatCurrency(maxLoss)}</div>
      </div>

      {outsideBreakevens.length > 0 ? (
        <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5, fontSize: "0.8rem" }}>
          Breakeven outside expected range: {outsideBreakevens.map((value) => formatCurrency(value)).join(" / ")}.
        </div>
      ) : null}

      {expectedRange.provenance_notes ? (
        <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5, fontSize: "0.8rem" }}>
          {expectedRange.provenance_notes}
        </div>
      ) : null}

      <div style={{ marginTop: 8, color: "var(--op-muted, #7a8999)", lineHeight: 1.5, fontSize: "0.8rem" }}>
        {DISCLAIMER_COPY} Range is based on available provider data and assumptions.
      </div>
    </section>
  );
}
