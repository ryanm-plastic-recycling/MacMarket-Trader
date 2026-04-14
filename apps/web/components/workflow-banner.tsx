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
};

function stepTone(step: GuidedStep, current: GuidedStep): "completed" | "current" | "pending" {
  const stepIdx = GUIDED_STEPS.indexOf(step);
  const currentIdx = GUIDED_STEPS.indexOf(current);
  if (stepIdx < currentIdx) return "completed";
  if (stepIdx === currentIdx) return "current";
  return "pending";
}

export function WorkflowBanner({ current, state, nextHref, nextLabel, backHref, backLabel, compact = false }: Props) {
  const query = buildGuidedQuery(state);

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
        <span>symbol: {state.symbol ?? "-"}</span>
        <span>strategy: {state.strategy ?? "-"}</span>
        <span>market: {state.marketMode ?? "equities"}</span>
        <span>source: {state.source ?? "-"}</span>
        <span>rec: {state.recommendationId ?? "-"}</span>
        <span>replay: {state.replayRunId ?? "-"}</span>
        <span>order: {state.orderId ?? "-"}</span>
      </div>
      <div className="op-workflow-actions">
        {backHref && backLabel ? <Link className="op-btn op-btn-ghost" href={`${backHref}?${query}`}>{backLabel}</Link> : <span />}
        {nextHref && nextLabel ? <Link className="op-btn op-btn-primary" href={`${nextHref}?${query}`}>{nextLabel}</Link> : null}
      </div>
    </section>
  );
}
