"use client";

import Link from "next/link";

import { GUIDED_STEPS, type GuidedFlowState, type GuidedStep, buildGuidedQuery } from "@/lib/guided-workflow";

type Props = {
  current: GuidedStep;
  state: GuidedFlowState;
  nextHref?: string;
  nextLabel?: string;
  backHref?: string;
  backLabel?: string;
  compact?: boolean;
  nextDisabled?: boolean;
  nextDisabledReason?: string;
};

function stepTone(step: GuidedStep, current: GuidedStep): "completed" | "current" | "pending" {
  const stepIdx = GUIDED_STEPS.indexOf(step);
  const currentIdx = GUIDED_STEPS.indexOf(current);
  if (stepIdx < currentIdx) return "completed";
  if (stepIdx === currentIdx) return "current";
  return "pending";
}

export function WorkflowBanner({ current, state, nextHref, nextLabel, backHref, backLabel, compact = false, nextDisabled = false, nextDisabledReason }: Props) {
  const query = buildGuidedQuery(state);

  // Compose a single primary context line: SYMBOL · strategy · market mode
  const primaryParts: string[] = [];
  if (state.symbol) primaryParts.push(state.symbol);
  if (state.strategy) primaryParts.push(state.strategy);
  if (state.marketMode) primaryParts.push(state.marketMode);
  const primaryContext = primaryParts.join(" · ");

  const chips: { key: string; label: string }[] = [];
  if (primaryContext) chips.push({ key: "primary", label: primaryContext });
  if (state.source) chips.push({ key: "source", label: `via ${state.source}` });
  if (state.recommendationId) chips.push({ key: "rec", label: `Rec #${state.recommendationId}` });
  if (state.replayRunId) chips.push({ key: "replay", label: `Replay #${state.replayRunId}` });
  if (state.orderId) chips.push({ key: "order", label: `Order #${state.orderId}` });

  const missingLineage = state.guided && (!state.recommendationId || (current === "Paper Order" && !state.replayRunId));
  const disabledLabel = nextDisabledReason ?? "Complete required lineage in this step first.";

  return (
    <section className={`op-workflow-banner ${state.guided ? "is-sticky" : ""} ${compact ? "is-compact" : ""}`} data-testid="workflow-banner">
      <div className="op-workflow-steps">
        {GUIDED_STEPS.map((step) => (
          <div key={step} className={`op-workflow-step is-${stepTone(step, current)}`} data-testid={`workflow-step-${step.toLowerCase().replace(/\s+/g, "-")}`}>
            {step}
          </div>
        ))}
      </div>
      <div className="op-workflow-context">
        {chips.map((chip) => <span key={chip.key}>{chip.label}</span>)}
        {missingLineage ? <span style={{ color: "#f7b267", borderColor: "#785931" }}>lineage incomplete</span> : null}
      </div>
      <div className="op-workflow-actions">
        {backHref && backLabel ? <Link className="op-btn op-btn-ghost" href={`${backHref}?${query}`}>{backLabel}</Link> : <span />}
        {nextHref && nextLabel ? (nextDisabled ? <button className="op-btn op-btn-primary" disabled title={disabledLabel}>{nextLabel}</button> : <Link className="op-btn op-btn-primary" href={`${nextHref}?${query}`}>{nextLabel}</Link>) : null}
      </div>
    </section>
  );
}
