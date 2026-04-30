import React from "react";

import { getGlossaryTerm, type GlossaryTermKey } from "@/lib/glossary";

type MetricHelpProps = {
  term: GlossaryTermKey | string;
  label?: string;
};

type MetricLabelProps = MetricHelpProps & {
  label: string;
};

const muted = "var(--op-muted, #7a8999)";

export function MetricHelp({ term, label }: MetricHelpProps) {
  const entry = getGlossaryTerm(term);
  if (!entry) return null;

  const summaryLabel = label ?? entry.label;

  return (
    <details
      style={{
        display: "inline-block",
        position: "relative",
        verticalAlign: "middle",
      }}
    >
      <summary
        aria-label={`Help: ${summaryLabel}`}
        title={`Help: ${entry.title}`}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 18,
          height: 18,
          borderRadius: 999,
          border: "1px solid var(--op-border, #1e2d3d)",
          color: muted,
          cursor: "pointer",
          fontSize: "0.72rem",
          fontWeight: 700,
          lineHeight: 1,
          listStyle: "none",
          userSelect: "none",
        }}
      >
        i
      </summary>
      <div
        role="note"
        style={{
          position: "absolute",
          zIndex: 20,
          right: 0,
          top: 24,
          width: 280,
          maxWidth: "min(280px, calc(100vw - 32px))",
          padding: "10px 12px",
          borderRadius: 8,
          border: "1px solid var(--op-border, #1e2d3d)",
          background: "var(--card-bg, #101923)",
          boxShadow: "0 10px 28px rgba(0, 0, 0, 0.32)",
          color: "var(--op-text, #e5edf5)",
          fontSize: "0.78rem",
          lineHeight: 1.45,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{entry.title}</div>
        <div>{entry.definition}</div>
        {entry.formula ? (
          <div style={{ marginTop: 6 }}>
            <strong>Formula:</strong> {entry.formula}
          </div>
        ) : null}
        {entry.example ? (
          <div style={{ marginTop: 6 }}>
            <strong>Example:</strong> {entry.example}
          </div>
        ) : null}
        {entry.caveat ? (
          <div style={{ marginTop: 6, color: muted }}>
            <strong>Not this:</strong> {entry.caveat}
          </div>
        ) : null}
      </div>
    </details>
  );
}

export function MetricLabel({ label, term }: MetricLabelProps) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span>{label}</span>
      <MetricHelp term={term} label={label} />
    </span>
  );
}
