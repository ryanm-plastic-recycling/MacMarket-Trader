import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="op-page-header">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div className="op-row">{actions}</div> : null}
    </div>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="op-card">
      {title ? <h3>{title}</h3> : null}
      {children}
    </section>
  );
}

export function StatusBadge({ tone = "neutral", children }: { tone?: "good" | "warn" | "bad" | "neutral"; children: ReactNode }) {
  return <span className={`op-badge op-badge-${tone}`}>{children}</span>;
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="op-empty">
      <strong>{title}</strong>
      <p>{hint}</p>
    </div>
  );
}

export function ErrorState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="op-error">
      <strong>{title}</strong>
      <p>{hint}</p>
    </div>
  );
}

export function InlineFeedback({
  state,
  message,
  retryLabel,
  onRetry,
}: {
  state: "idle" | "loading" | "success" | "error";
  message?: string;
  retryLabel?: string;
  onRetry?: () => void;
}) {
  if (state === "idle" && !message) return null;
  const tone = state === "success" ? "good" : state === "error" ? "bad" : "neutral";
  return (
    <div className="op-row">
      <StatusBadge tone={tone}>
        {state === "loading" ? "working…" : state}
      </StatusBadge>
      {message ? <span>{message}</span> : null}
      {state === "error" && onRetry ? <button onClick={onRetry}>{retryLabel ?? "Retry"}</button> : null}
    </div>
  );
}
