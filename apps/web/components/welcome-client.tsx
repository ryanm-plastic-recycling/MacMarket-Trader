"use client";

import React from "react";
import ReactMarkdown from "react-markdown";

const proseStyles = {
  fontFamily: "Inter, Arial, sans-serif",
  color: "var(--text)",
  lineHeight: 1.65,
  fontSize: 14.5,
} as const;

export function WelcomeClient({ markdown }: { markdown: string }) {
  return (
    <>
      {/* Print-friendly CSS — strips chrome and hides interactive elements when
          the operator triggers Print. Scoped via @media print so screen rendering
          is unaffected. */}
      <style>{`
        @media print {
          .op-shell, .op-aside, .op-topbar, .op-workflow-banner,
          [data-print-hide="true"] { display: none !important; }
          .op-content { padding: 0 !important; }
          .op-card { border: none !important; background: white !important; color: black !important; }
          .welcome-prose { color: black !important; }
          .welcome-prose h1, .welcome-prose h2, .welcome-prose h3 { color: black !important; }
          .welcome-prose code, .welcome-prose pre { background: #f4f4f4 !important; color: #1a1a1a !important; }
          .welcome-prose blockquote { color: #333 !important; border-left-color: #999 !important; }
        }
      `}</style>

      <div className="op-row" data-print-hide="true" style={{ marginBottom: 12 }}>
        <button
          onClick={() => window.print()}
          className="op-btn op-btn-secondary"
          aria-label="Print this welcome guide"
        >
          🖨 Print this page
        </button>
      </div>

      <div className="op-card welcome-prose" style={{ padding: 28, ...proseStyles }}>
        <ReactMarkdown
          components={{
            h1: ({ children }) => (
              <h1 style={{ fontSize: 28, fontWeight: 700, margin: "4px 0 18px 0", lineHeight: 1.2 }}>{children}</h1>
            ),
            h2: ({ children }) => (
              <h2
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  margin: "28px 0 10px 0",
                  paddingBottom: 6,
                  borderBottom: "1px solid var(--card-border, #2a3440)",
                  color: "#21c06e",
                }}
              >
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: "20px 0 8px 0" }}>{children}</h3>
            ),
            p: ({ children }) => (
              <p style={{ margin: "10px 0", lineHeight: 1.65 }}>{children}</p>
            ),
            ul: ({ children }) => (
              <ul style={{ margin: "10px 0", paddingLeft: 24, lineHeight: 1.65 }}>{children}</ul>
            ),
            ol: ({ children }) => (
              <ol style={{ margin: "10px 0", paddingLeft: 24, lineHeight: 1.65 }}>{children}</ol>
            ),
            li: ({ children }) => <li style={{ margin: "4px 0" }}>{children}</li>,
            code: ({ children, className }) => {
              const inline = !className;
              if (inline) {
                return (
                  <code
                    style={{
                      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                      fontSize: 13,
                      background: "rgba(33, 192, 110, 0.08)",
                      color: "#21c06e",
                      padding: "1px 6px",
                      borderRadius: 4,
                    }}
                  >
                    {children}
                  </code>
                );
              }
              return <code className={className}>{children}</code>;
            },
            pre: ({ children }) => (
              <pre
                style={{
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: 13,
                  background: "var(--input-bg, #0e151d)",
                  border: "1px solid var(--card-border, #2a3440)",
                  borderRadius: 6,
                  padding: "12px 14px",
                  overflowX: "auto",
                  margin: "12px 0",
                  lineHeight: 1.5,
                }}
              >
                {children}
              </pre>
            ),
            blockquote: ({ children }) => (
              <blockquote
                style={{
                  margin: "14px 0",
                  padding: "8px 14px",
                  borderLeft: "3px solid #21c06e",
                  background: "rgba(33, 192, 110, 0.05)",
                  color: "var(--muted, #9fb0c3)",
                  fontStyle: "italic",
                }}
              >
                {children}
              </blockquote>
            ),
            hr: () => (
              <hr
                style={{
                  border: "none",
                  borderTop: "1px solid var(--card-border, #2a3440)",
                  margin: "24px 0",
                }}
              />
            ),
            a: ({ children, href }) => (
              <a href={href} style={{ color: "#21c06e", textDecoration: "underline" }}>
                {children}
              </a>
            ),
            strong: ({ children }) => (
              <strong style={{ color: "var(--text)", fontWeight: 700 }}>{children}</strong>
            ),
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    </>
  );
}
