# Model Inventory

This inventory describes current decision engines and model-adjacent systems
for validation planning. It is an internal readiness artifact, not a claim of
external model approval or investment performance.

## Setup Engines

- Component: deterministic setup engine.
- Purpose: convert structured event, regime, and technical context into
  setup type, direction, entry zone, invalidation, targets, and time stop.
- Current evidence: recommendation contract tests, replay tests, and
  generated recommendation payload provenance.
- Current gap: no formal setup-engine version register or independently
  reviewed historical validation packet.

## Ranking And Scoring Logic

- Component: deterministic ranked queue and scoring logic.
- Purpose: rank candidate symbols and strategies using deterministic fit,
  regime, liquidity, volatility, confidence, expected RR, and recency factors.
- Current evidence: ranked queue tests, recommendation workflow tests, and
  already-open awareness tests.
- Current gap: no walk-forward benchmark report against SPY/QQQ or simple
  strategy baselines.

## Risk Sizing

- Component: deterministic risk engine and paper-order sizing constraints.
- Purpose: compute risk-budget sizing, max notional caps, stop-distance risk,
  and approval/rejection constraints.
- Current evidence: risk engine tests, paper sizing tests, order lifecycle
  tests, and paper sandbox reset tests.
- Current gap: no formal capital-assumption register for validation reports.

## Market Risk Calendar

- Component: deterministic market risk calendar and sit-out guardrails.
- Purpose: classify warning/restriction/block states for macro/event risk.
- Current evidence: risk-calendar tests and route/UI integration tests.
- Current gap: no recurring attribution report by risk-calendar state.

## Active Paper Position Review

- Component: deterministic active paper position review.
- Purpose: classify open equity paper positions for review-only management
  context without automated exits or scale-in automation.
- Current evidence: Active Paper Position Review tests and Orders UI tests.
- Current gap: no longitudinal validation of action classifications versus
  later paper outcomes.

## LLM Explanation Boundary

- Component: OpenAI/mock LLM explanation and Opportunity Intelligence sidecar.
- Purpose: summarize, compare, and explain deterministic outputs.
- Boundary: LLMs cannot alter approval, side, entry, stop, target, sizing,
  risk-calendar decisions, order creation, or paper position classifications.
- Current evidence: LLM validation/fallback tests and provider-health
  provenance.
- Current gap: prompt/version register and adversarial prompt-injection
  validation corpus remain incomplete.

## Current Versioning Gaps

- No formal setup-engine version register.
- No formal ranking-engine version register.
- No formal risk-engine version register beyond code/package version.
- No prompt version register.
- No validation dataset version register.
- No recurring drift report for provider/model/rules changes.
