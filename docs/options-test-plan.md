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
- Analysis integration moved to `10A1`; richer replay placement and
  provider-depth polish remain future work only if explicitly reopened

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
- remaining future coverage should follow richer replay placement or
  provider-depth work only if those scopes are explicitly reopened

## Phase 10 planned test areas

Phase 10 is planning/polish first. Tests should scale to the risk of the
specific slice and continue to prove equity behavior and current options
lifecycle behavior did not move.

Current status:

- `10A1` is complete for the frontend-only Analysis Expected Range
  visualization reuse. Coverage stays focused on Analysis wiring/copy plus the
  reusable component's existing computed, blocked, missing, invalid-number, and
  safety-copy render tests.
- `10B1` is complete for frontend-only Orders durable paper-options
  display/readability polish. Coverage focuses on display-only purpose copy,
  open/closed status clarity, commission reminders, expandable leg details,
  provider/source/as-of limitation copy, missing-value safety, and no
  live-routing or broker-execution implication.
- `10C1` is complete for the frontend-only explainable metric UX foundation.
  Coverage focuses on the required glossary registry terms, reusable
  metric-help rendering, unknown-term safety, commission guardrail copy,
  Expected Range research-only caveats, confidence/score non-probability
  wording, Provider readiness non-execution wording, and Settings integration.
- `10C2` is complete for Recommendations metric-help rollout. Coverage proves
  queue/detail `Score`, `RR`, and `CONF` labels use `MetricLabel`, options
  risk/lifecycle labels expose help for Expected Range, max profit/loss,
  breakevens, gross/net P&L, and options commissions, and safety wording still
  avoids probability, live-routing, and broker-execution implications.
- `10C3` is complete for Orders metric-help rollout. Coverage proves Orders
  equity P&L/fee labels use `MetricLabel`, durable paper-options rows expose
  help for gross/net P&L, options commissions, max profit/loss, breakevens,
  paper lifecycle, and leg-level result labels, and no new Orders actions,
  backend behavior, lifecycle math, or commission math are introduced.
- `10C4` is complete for Analysis and Replay metric-help rollout. Coverage
  proves Analysis options risk/source labels and Replay score, confidence,
  gross/net P&L, and fee labels use `MetricLabel`, while glossary safety copy
  still avoids probability, broker-simulation, live-routing, and execution
  implications.
- `10C5` is complete for the explainable metrics closure audit. Coverage now
  confirms the current in-context glossary/tooltips scope across Settings,
  Provider Health, Expected Range, Recommendations, Orders, Analysis, and
  Replay, with focused safety tests for provider readiness and replay payoff
  preview wording. Optional glossary/reference-page work remains deferred.
- `10W4` is complete for the additive symbol-universe schema/migration
  foundation. Coverage proves Alembic upgrade/downgrade for
  `user_symbol_universe` and `watchlist_symbols`, ORM metadata/create_all
  compatibility, active defaults, nullable provider metadata for manual
  symbols, unique constraints, snapshot-only watchlist membership without a
  `user_symbol_id`, and continued existing watchlist/schedule compatibility.

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
- `10B1` current coverage proves the section explains display-only durable
  paper lifecycle records saved from Recommendations
- `10B1` current coverage proves open paper position and manually closed paper
  position labels render clearly
- `10B1` current coverage proves gross P&L, opening/closing/total
  commissions, and net P&L render for closed rows when available
- `10B1` current coverage proves expandable leg details render action, right,
  strike, expiration, contracts, multiplier, entry/exit premiums, and
  leg-level gross/commission/net values safely
- `10B1` current coverage proves options commission copy says not multiplied
  by 100 and shows the contracts x legs x events formula
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
- note:
  `10C1` is an explainable metric UX foundation slice and does not close this
  replay/history checkpoint

### 10C1 explainable metric UX foundation

- glossary registry contains `rr`, `confidence`, `score`, `expected_range`,
  `dte`, `iv`, `open_interest`, `breakeven`, `max_profit`, `max_loss`,
  `gross_pnl`, `net_pnl`, `equity_commission_per_trade`,
  `options_commission_per_contract`, `provider_readiness`,
  `paper_lifecycle`, and `replay_payoff_preview`
- known `MetricHelp` / `MetricLabel` terms render compact help content
- unknown terms render nothing rather than crashing
- options commission help says per contract, per leg, per event, not per
  share, and not multiplied by 100
- Expected Range help says it does not change payoff math, approve execution,
  or represent probability of profit
- `CONF` and `Score` glossary copy does not describe either value as
  probability of profit
- Provider readiness glossary copy does not imply live routing or broker
  execution
- Settings page renders the commission help integrations
- broader Analysis, Recommendations, Replay, Orders, and glossary-page rollout
  remains future work

### 10C2 Recommendations metric-help rollout

- Recommendations queue headers and detail labels expose compact help for
  `Score`, `RR`, and `CONF` / confidence without changing scoring or
  recommendation generation
- Recommendations options risk cards expose help for Expected Range, max
  profit, max loss, breakevens, replay payoff preview, and paper lifecycle
- paper lifecycle result labels expose help for gross P&L, net P&L, and
  options commissions, including the not-multiplied-by-100 commission caveat
- confidence and score glossary copy still does not describe either value as
  probability of profit
- no live-routing, broker-execution, payoff-math, lifecycle-math, commission,
  schema, provider, or backend behavior changes are expected
- broader Analysis, Replay, Orders, and optional glossary-page rollout remains
  future work

### 10C3 Orders metric-help rollout

- Orders equity portfolio/projected outcome/closed-trade labels expose compact
  help for gross P&L, net P&L, and equity fees where those labels are visible
- durable paper-options section exposes help for max profit, max loss,
  breakevens, gross P&L, net P&L, opening commissions, closing commissions,
  total commissions, paper lifecycle, and leg-level gross/commission/net
  result labels
- options commission help includes the per-contract/per-leg/per-event wording
  and not-multiplied-by-100 caveat
- paper lifecycle help says persisted paper records do not mean external
  orders were sent
- no live-routing, broker-execution, new Orders actions, payoff-math,
  lifecycle-math, commission-math, schema, provider, or backend behavior
  changes are expected
- Analysis and Replay rollout is covered by `10C4`; optional glossary-page
  rollout remains future work

### 10C4 Analysis and Replay metric-help rollout

- Analysis options setup/research labels expose compact help for provider
  source/readiness, Expected Range / Expected Move, DTE, IV, breakevens, max
  profit, max loss, and confidence where those labels are visible
- Replay labels expose compact help for score, confidence, gross P&L, net
  P&L, and equity fee estimates where those labels are visible
- score and confidence glossary copy still does not describe either value as
  probability of profit
- Expected Range help still says it does not change payoff math or approve
  execution
- Replay-related help does not imply broker mark-to-market simulation,
  routing, or live execution
- no backend, replay behavior, recommendation scoring, schema, provider,
  lifecycle-math, payoff-math, commission-math, or equity behavior changes are
  expected
- optional glossary/reference-page rollout remains future work

### 10C5 explainable metrics closure audit

- Settings commission fields, Provider Health readiness, Expected Range,
  Recommendations score/risk labels, Orders P&L/commission labels, Analysis
  options risk/source labels, and Replay score/P&L/fee labels have current-scope
  `MetricHelp` / `MetricLabel` coverage
- glossary tests verify the required term registry, unknown-term safety, options
  commission per-contract/per-leg/per-event wording, Expected Range
  research-only wording, confidence/score non-probability wording, Provider
  readiness non-execution wording, and Replay payoff preview no
  broker-mark-to-market-simulation wording
- component tests verify compact native help markup that works via click/tap and
  keyboard-accessible summary behavior
- no backend, schema, provider, scoring, equity, lifecycle-math, payoff-math,
  commission-math, live-routing, broker-execution, symbol-discovery, watchlist,
  or probability behavior changes are expected
- optional glossary/reference-page rollout remains future work

### 10W4 symbol-universe schema foundation

- Alembic upgrade creates `user_symbol_universe` and `watchlist_symbols`
- Alembic downgrade removes both new additive tables cleanly
- ORM metadata/create_all includes the new models
- manual symbol rows can exist without provider metadata
- `active` defaults to true on user-symbol and watchlist-membership rows
- unique `(app_user_id, normalized_symbol)` prevents duplicate canonical
  symbols per user
- unique `(watchlist_id, normalized_symbol)` prevents duplicate membership
  snapshots per watchlist
- `watchlist_symbols.user_symbol_id` remains nullable so future membership rows
  can store a symbol snapshot before resolver/backfill wiring exists
- existing `/user/watchlists` JSON/list behavior remains compatible
- existing strategy report schedule payload symbols still run
- no frontend UI, provider search, recommendation generation, schedule
  execution, equity/options lifecycle, commission, live-routing, or
  broker-execution behavior changes are expected

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
