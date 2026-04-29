// Server component — pre-auth and holding-page brand strip.
// Renders the MacMarket lockup PNG plus an optional tagline above whatever
// page content follows. No "use client" needed — pure HTML/CSS.

type BrandHeaderProps = { tagline?: string };

export function BrandHeader({ tagline }: BrandHeaderProps) {
  return (
    <div
      style={{
        padding: "24px 28px",
        background: "var(--op-surface, var(--card-bg, #0f1722))",
        borderBottom: "1px solid var(--op-border, var(--border, #2b3642))",
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 6,
      }}
    >
      <img
        src="/brand/square_console_ticks_lockup_dark.png"
        alt="MacMarket Trader"
        height={36}
        style={{ display: "block", height: 36, width: "auto", border: 0 }}
      />
      {tagline ? (
        <p
          style={{
            margin: 0,
            fontSize: 12,
            color: "var(--muted, #9fb0c3)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            fontWeight: 600,
          }}
        >
          {tagline}
        </p>
      ) : null}
    </div>
  );
}
