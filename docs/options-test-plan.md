# Phase 8 Options Test Plan

Last updated: 2026-04-29

## Purpose

This document defines the test matrix for future Phase 8 implementation.

It separates:

- backend replay/math and lifecycle tests
- frontend research/replay/lifecycle rendering tests
- equity regression gates that must stay green

## Guiding rule

Every options slice must prove two things:

1. the new options behavior works for the supported structure
2. current equity behavior did not regress

## Existing regression anchors

Current repo anchors that should stay green during Phase 8 work:

- `tests/test_replay_engine.py`
- `tests/test_phase1_workflow_hardening.py`
- `tests/test_recommendations_api.py`
- `tests/test_strategy_reports.py`
- `tests/test_market_data_service.py`
- frontend recommendations/options preview tests

## 8C backend tests

Required for `8C2` and `8C3`:

- pure payoff math helper tests
- vertical debit spread payoff tests
- iron condor payoff tests
- optional long call / long put primitive tests if helpers use them
- blocked preview tests:
  - missing premium
  - incomplete legs
  - unsupported structure
- commission estimate tests if `commission_per_contract` is included in preview

Equity regression tests required alongside 8C:

- equity replay engine tests
- replay workflow hardening tests
- no unexpected change to equity replay route behavior

## 8C frontend tests

Required for replay preview UI:

- options replay preview renders structure summary
- options replay preview renders max profit/loss and breakevens when available
- blocked reasons render clearly
- expected range remains contextual and does not read like payoff math
- blocked or omitted expected-range reasons render clearly
- missing values render as `Unavailable` or `-`
- staging/order CTAs remain suppressed

## 8D backend tests

Required now for `8D2` schema foundation:

- dedicated schema/migration tests for `paper_option_*` tables
- model default tests for `execution_enabled=false`, `quantity=1`, and
  `multiplier=100`
- focused upgrade/downgrade coverage for the dedicated options schema revision

Required now for `8D3` repository/service contracts:

- repository create/fetch tests for option paper orders and legs
- repository create/fetch tests for option paper positions and legs
- repository create/fetch tests for option paper trades and legs
- open-position query scoping tests by user and status
- validation-block tests for naked short and unsupported expiration patterns
- regression proof that equity paper lifecycle tests remain green

Required now for `8D4` open paper option structure behavior:

- open paper option structure tests for supported defined-risk inputs
- order and position header/leg persistence tests through the open-only path
- user-scoping tests for created option paper orders and positions
- response-contract tests for:
  - `market_mode=options`
  - `execution_enabled=false`
  - `persistence_enabled=true`
  - paper-only disclaimer presence
- blocked naked-short and invalid-leg-data tests proving nothing persists
- regression proof that no equity orders, positions, trades, recommendations,
  or replay runs are created by the options open path

Required now for `8D5` manual close paper option structure behavior:

- manual close lifecycle tests for supported defined-risk inputs
- gross P&L tests for both profitable and losing closes
- trade header and trade-leg persistence tests through the close path
- position and position-leg closed-state persistence tests
- blocked double-close tests
- blocked wrong-user tests
- blocked negative exit-premium tests
- blocked partial-leg close tests
- regression proof that no equity orders, positions, trades, recommendations,
  or replay runs are created by the options close path
- regression proof that existing equity close lifecycle tests remain green

Required now for `8D6` options contract-commission modeling:

- options close with zero commission proves `net_pnl == gross_pnl`
- options close with nonzero commission proves
  `net_pnl = gross_pnl - total_commissions`
- multi-leg commission math proves commission is per contract per leg, not per
  share or contract multiplier
- open-response tests prove `commission_per_contract` and opening commission
  visibility
- regression proof that Phase 7 equity `commission_per_trade` behavior remains
  green

Required later for options paper lifecycle:

- expiration-settlement lifecycle tests
- debit versus credit handling tests
- defined-risk validation tests
- blocked naked-short tests
- blocked unsupported assignment/exercise automation tests

Equity regression tests required alongside 8D:

- current paper order lifecycle tests
- current close/reopen tests
- current fee-preview tests

## 8D frontend tests

Required now for `8D7` frontend operator UI:

- settings page renders explicit `commission_per_contract` guardrails:
  - per contract
  - not per share
  - do not multiply by 100
  - formula plus compact example
- Recommendations options research preview renders a separate paper option
  lifecycle panel
- replay payoff preview remains visually distinct from persisted paper
  lifecycle actions
- paper option open UI disables safely for unsupported or incomplete
  structures
- same-origin frontend proxy tests cover:
  - open route
  - close route
  - success and failure pass-through behavior
- helper tests cover:
  - paper open request shaping
  - commission estimate math
  - no `x100` commission mistake
- if manual close UI is rendered:
  - per-leg exit premium inputs appear
  - gross/commission/net close summary renders safely
  - missing values remain `Unavailable` or `-`
  - replay preview stays visually distinct from the persisted paper lifecycle
  - operator-facing paper lifecycle copy avoids live-routing, brokerage, and
    equity staging language

Required later for broader options paper lifecycle UI:

- durable Orders parity for open option positions/trades
- expiration-status display
- broader multi-position operator workflow coverage

## 8E frontend tests

Required now for `8E1` operator risk UX foundation:

- risk summary renders max profit/loss and breakevens
- missing risk values render as `Unavailable` or `-`
- Expected Range copy remains contextual and does not read like payoff math
- warning/caveat copy renders for paper-only, preview-only, and missing-data
  states
- replay payoff preview and persisted paper lifecycle stay visibly distinct
- manual-close commission reminder remains visible when lifecycle results are
  present
- stale or unavailable data does not look healthy

Required now for `8E2` broader provider/data-quality coverage:

- provider/source/as-of labels render safely when present on the current
  Recommendations options surface
- missing source/as-of values render `Source unavailable` / `As-of
  unavailable` safely
- chain-preview unavailable warnings render with provider-plan/payload wording
- blocked or omitted Expected Range reasons stay visible without reading like
  payoff math
- SPX/NDX provider-plan caveats appear when index symbols are in play
- stale/unavailable provider context does not read like live or execution
  approval

Required now for `8E3` guided workflow clarity:

- guided options stepper renders and reflects preview/open/manual-close/result
  state correctly
- replay payoff preview remains labeled read-only/non-persisted
- paper save wording states that it creates paper-only records and does not
  place a broker order
- manual close rows explain exit premium, provide a compact example, and show
  long/short direction hints
- post-close result state renders a clear success/result card with
  gross/opening/closing/total/net values
- progressive disclosure keeps provider/warning detail available without
  turning the page back into a wall of text

## Route and CTA safety tests

Phase 8 should continue to prove:

- options mode does not call queue/promote routes in 8B or 8C
- options mode does not expose equity staging/order CTAs outside the dedicated
  8D paper lifecycle panel
- options mode does not expose live-routing language

If dedicated options replay preview routes are added later, add tests proving:

- they do not create equity replay DB rows in the initial 8C slice
- they do not reuse equity order/fill semantics

## Acceptance gates by slice

### 8C gate

- payoff math tests pass
- replay preview rendering tests pass
- equity replay regression tests pass

### 8D gate

- options lifecycle tests pass
- options lifecycle UI tests pass
- equity paper workflow regressions pass

## Manual smoke checklist

Use this short manual pass when closing the current `8D` scope:

1. Set `commission_per_contract` in Settings and confirm the page says "Not
   per share. Do not multiply by 100."
2. Open Recommendations in options mode and confirm the research preview loads
   with expected range context.
3. Run Replay payoff preview and confirm it stays read-only and
   non-persisted.
4. Confirm the `Structure risk` card shows max profit/loss, breakevens,
   Expected Range status, replay-preview status, and paper lifecycle status
   without mixing the three surfaces together.
5. Confirm the same `Structure risk` card also shows workflow source, chain
   source/as-of, and Expected Range provenance when available, and safe
   `Source unavailable` / `As-of unavailable` copy when those fields are not
   present on the payload.
6. Open paper option structure and verify the page shows estimated opening and
   open + close commissions.
7. Enter exit premium per leg and manually close the paper structure.
8. Verify gross P&L, opening commissions, closing commissions, total
   commissions, and net P&L.
9. Verify the page stays paper-only and does not present live-trading or
   brokerage-routing language.
10. Verify the guided stepper advances sensibly from structure review to
    payoff preview, paper save, manual close, and result review.

### 8E gate

- `8E1`, `8E2`, and `8E3` risk UX tests pass
- replay-preview and paper-lifecycle separation remains explicit
- provider/source/as-of and data-quality warnings remain explicit
- manual-close inputs and post-close results are operator-readable without
  implying broker execution
- CTA suppression boundaries remain correct

Current status:

- the `8E` gate is satisfied for the current Recommendations options surface
- `8F` remains open for the broader Phase 8 closure pass

### 8F gate

- supported defined-risk options flow is testable end to end for the intended
  paper-only scope
- deferred items remain documented rather than implied complete

## Suggested future test file direction

Backend:

- `tests/test_options_payoff_math.py`
- `tests/test_options_replay_preview.py`
- `tests/test_options_paper_schema.py`
- `tests/test_options_paper_repository.py`
- `tests/test_options_paper_lifecycle.py`

Frontend:

- options replay preview tests near the Replay workspace code
- options lifecycle/risk component tests near their feature components

Keep these additions mode-specific and avoid rewriting current equity tests
unless a true regression requires it.
