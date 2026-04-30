# Phase 8 Options Test Plan

Last updated: 2026-04-30

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
- reference-only chain-preview copy explains that missing `last` / `volume`
  fields can reflect current provider/source/tier limits and do not change
  payoff math
- incomplete call-only or put-only chain snapshots render a compact warning
  for defined-risk structure review
- blocked or omitted Expected Range reasons stay visible without reading like
  payoff math
- SPX/NDX provider-plan caveats appear when index symbols are in play
- stale/unavailable provider context does not read like live or execution
  approval

Required now for `8E3` guided workflow clarity:

- guided options stepper renders and reflects preview/open/manual-close/result
  state correctly
- the final step reads as a paper-close result rather than a generic saved
  result, and it stays future/pending until manual close actually happens
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
11. Open Orders and confirm the dedicated `Paper Options Positions` section
    shows the saved open paper option position outside Recommendations.
12. After manual close, confirm Orders shows the closed paper result with
    gross, opening commissions, closing commissions, total commissions, and
    net P&L.

### 8E gate

- `8E1`, `8E2`, and `8E3` risk UX tests pass
- replay-preview and paper-lifecycle separation remains explicit
- provider/source/as-of and data-quality warnings remain explicit
- manual-close inputs and post-close results are operator-readable without
  implying broker execution
- CTA suppression boundaries remain correct

Current status:

- the `8E` gate is satisfied for the current Recommendations options surface
- the `8F` gate is satisfied for the current scoped paper-first options
  capability

### 8F gate

- supported defined-risk options flow is testable end to end for the intended
  paper-only scope
- deferred items remain documented rather than implied complete

Current closure note:

- Phase 8 is complete for the current scoped paper-first options capability
- this does not include expiration settlement, assignment/exercise
  automation, persisted options recommendations, advanced Expected Move
  visualization, or live routing/execution
- durable Orders visibility for paper option positions/trades now lands in
  `9B`, while broader provider/source/as-of parity remains `9C`

## Phase 9 planned test areas

Planning note:

- `9A` is planning only
- `9B` is now implemented/current
- `9C1` is now implemented for the updated Analysis, Orders durable
  paper-options, and Provider Health surfaces
- `9C` is now closed for the current provider/source/as-of parity scope
- `9D1` design is complete
- `9D2` is now implemented/current for the reusable frontend Expected Range
  visualization component plus first Recommendations integration
- `9D` is now closed for the current Recommendations Expected Range
  visualization scope
- Phase 9 is now closed for the current options operator parity,
  provider/source/as-of, and Recommendations Expected Range visualization
  scope
- optional Analysis integration, richer replay placement, and provider-depth
  polish remain future work only if explicitly reopened

### 9B current tests — durable operator visibility

- backend list endpoint returns only the current user's paper option
  positions and folds in closed-trade gross/commission/net fields when
  present
- open paper option positions render on Orders with clear paper-only labels
  and pending-manual-close messaging
- closed paper option trades render on Orders with structure, leg,
  gross/opening/closing/total/net visibility
- equity Orders behavior and copy remain unchanged while options records gain
  their own durable operator surface
- missing position/trade fields still render as `Unavailable` or `-`

### 9C current and future tests - provider/source/as-of parity

- Analysis options Expected Range renders method, reference-price provenance,
  source notes, and as-of fallback safely from existing setup payload fields
- Analysis chain preview renders source/as-of, provider-plan caveats,
  reference-only notes, incomplete side warnings, and safe missing field values
- Orders durable paper-options rows render a muted limitation note rather than
  treating absent provider metadata as an error
- Provider Health options/index caveats remain readiness-only and do not imply
  routing or execution
- provider/source/as-of labels remain consistent across research preview,
  payoff preview, paper lifecycle, and future durable options listings
- reference-only snapshots, missing `last` / `volume`, incomplete call/put
  sides, and stale-data caveats stay explicit across those surfaces
- missing market fields are never interpreted as `0`
- closure audit validation confirms the current scoped surfaces do not add
  provider probes, live routing, expiration settlement, or assignment/exercise

### 9D future tests — Expected Move visualization

- Expected Move remains explicitly contextual and never reads like payoff math
- visualization uses the current status/method/bounds/reason contract without
  implying execution approval
- visualization does not alter replay or paper lifecycle math semantics
- `9D2` current coverage proves computed ranges render lower/upper labels and
  breakeven markers
- `9D2` current coverage proves blocked expected ranges render the blocked
  reason
- `9D2` current coverage proves missing expected ranges render an unavailable
  state
- `9D2` current coverage proves invalid numeric values do not render as
  `null`, `undefined`, `NaN`, or `Infinity`
- `9D2` current coverage proves safety copy says Expected Range does not
  change payoff math or approve execution
- `9D2` current coverage checks against probability-of-profit, live-trading,
  routing, and trade-signal claims
- closure coverage confirms derived range-midpoint copy does not imply an
  actual current/reference price when the payload does not carry one
- remaining future coverage should follow optional Analysis integration,
  richer replay placement, or provider-depth work only if those scopes are
  explicitly reopened

## Phase 10 planned test areas

Phase 10 is planning/polish first. Tests should scale to the risk of the
specific slice and continue to prove equity behavior and current options
lifecycle behavior did not move.

### 10A safe options UX/operator polish

- Analysis optional Expected Range visualization renders computed lower/upper
  bounds when existing fields are present
- blocked/missing Analysis expected range renders muted unavailable state and
  reason when available
- source/as-of, method/provenance, expiration/DTE, and breakevens render
  safely from existing payload fields
- no `null`, `undefined`, `NaN`, `Infinity`, probability-of-profit,
  execution-approval, live-routing, or broker-order language appears
- replay payoff visualization polish, if added, remains read-only and
  non-persisted

### 10B durable Orders options polish

- open and closed durable paper-options rows remain separate from equity
  Orders rows
- added filters, grouping, or summary copy preserve paper-only labels and
  durable provider-metadata limitation copy
- missing expiration/DTE, gross, commissions, net P&L, source, and as-of fields
  render as `Unavailable` or `-`
- no close/open/stage actions appear unless a later lifecycle phase explicitly
  authorizes them
- equity Orders tests remain green

### 10C replay/history design checkpoint

- docs-only by default; if later implementation is approved, tests must prove
  read-only preview still creates no replay runs, recommendations, orders,
  positions, or trades
- future mode-native persistence tests must not reuse equity replay semantics
  silently

### 10D expiration settlement design checkpoint

- docs-only by default; until implementation is explicitly approved,
  expiration settlement requests must continue to reject with the existing
  unsupported response
- any later implementation needs settlement-price fixtures, user-scoping,
  no-double-close, no-assignment/exercise, no-naked-short, and equity lifecycle
  regression tests

### 10E provider-depth/readiness planning

- docs/copy tests should keep provider readiness separate from execution
  enablement
- any later probe implementation must have unavailable/degraded/blocked states,
  no paid-plan-specific assumptions, and no routing/execution implication

### 10F crypto architecture planning

- docs-only by default
- later implementation must test market-mode separation, 24/7 session handling,
  provider/fallback labeling, and no equities/options lifecycle leakage

### 10G closure

- rerun touched frontend/backend tests for any implemented slices
- confirm roadmap/docs identify completed slices vs deferred future work
- confirm safety language still says paper-first, no live routing, no real
  brokerage execution, and Expected Range remains research context only

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
