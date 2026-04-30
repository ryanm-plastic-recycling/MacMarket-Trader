# Phase 8E Options Risk UX Design

Last updated: 2026-04-30

## Purpose

This document defines the operator-facing risk UX for the current
Recommendations options surface and its planned follow-on slices.

The current Recommendations options surface now satisfies `8E1` through `8E3`
plus closure review for the scoped risk/operator UX pass. `8F` now confirms
that this current Recommendations risk/operator UX surface is closed as part
of the scoped paper-first Phase 8 options capability. It does not require a
full charting implementation in the first slice, and later options surfaces
may still add more depth.

Current implementation note:

- `8D7` and `8D8` now close the first paper-options operator UI scope inside
  Recommendations
- the replay payoff preview stays visibly read-only/non-persisted and the
  paper lifecycle panel stays visibly separate and paper-only
- commission-per-contract guardrails now appear in both Settings and the
  paper lifecycle panel, explicitly stating that commission is not multiplied
  by 100
- `8E1` now adds a compact `Structure risk` card inside Recommendations that
  surfaces structure type, debit/credit, max profit/loss, breakevens,
  expiration / DTE, Expected Range status, replay-preview status, paper
  lifecycle state, and compact warnings without collapsing research, replay,
  and paper lifecycle into one surface
- `8E2` now extends that same Recommendations surface with compact provider
  and data-quality context: underlying workflow source, chain source/as-of,
  Expected Range provenance/as-of, safe `Source unavailable` / `As-of
  unavailable` rendering, and provider-plan/payload warnings for missing
  chain, IV, Greeks, open interest, and index-data caveats
- `8E3` now adds a guided operator workflow layer on top of that same
  Recommendations surface: a stepper for structure -> payoff preview ->
  paper save -> manual close -> result, clearer paper-only save wording,
  explicit exit-premium instructions, a stronger post-close result card, and
  lighter progressive disclosure for detailed warnings/provider context
- post-`8E` smoke-test polish now clarifies that the Recommendations chain
  preview is a lightweight reference snapshot: missing `last` / `volume`
  fields can reflect current provider/source/tier limits, incomplete
  call-only or put-only previews are called out explicitly, and guided Step 5
  is labeled as a paper-close result rather than a generic saved result
- post-Phase 8 the next UX maturity target is not live execution; it is
  durable operator visibility for paper option positions/trades outside
  Recommendations plus consistent provider/source/as-of and missing-data
  warning presentation across future options surfaces
- `9B` now adds a durable paper-options visibility section on Orders, while
  broader multi-surface parity and richer expiration/status views remain
  future work
- `9C1` now extends provider/source/as-of parity to the practical existing
  surfaces outside Recommendations: Analysis options Expected Range and chain
  preview context use existing payload metadata and safe fallbacks; Orders
  durable paper-options rows disclose that full provider/source metadata remains
  research-preview context; Provider Health carries options/index data caveats
  as readiness context only
- `9C` is now closed for the current scoped options surfaces after audit:
  Analysis, Recommendations, Orders durable paper-options rows, Provider
  Health, and operator guidance present source/as-of/provenance context,
  provider-plan caveats, and durable metadata limitations where existing
  payload fields support them
- `9D2` now adds the first reusable Expected Range visualization component
  inside Recommendations `Structure risk`, using existing payload fields only
  and keeping Expected Range explicitly research-only
- `9D` is now closed for the current Recommendations Expected Range
  visualization scope; Analysis integration later landed in `10A1`, while
  deeper provider/visual depth remains future work
- Phase 9 is now closed for the current options operator parity,
  provider/source/as-of, and Recommendations Expected Range visualization
  scope
- Phase 10 is the current planning/polish track. `10A1` is complete for the
  optional Analysis Expected Range visualization using existing payload fields
  and the current reusable component only. Orders polish and replay/payoff
  visualization polish remain safe only while they stay read-only, paper-only,
  and avoid lifecycle/math/provider behavior changes.

## UX goals

- keep options surfaces operator-grade, not retail-broker-like
- make defined-risk structure assumptions explicit
- make data-quality gaps obvious
- preserve paper-only and non-execution labeling
- avoid hiding risk behind dense terminology

## Required operator surfaces

### Strategy summary

Every supported options surface should later show:

- underlying symbol
- structure type
- expiration date
- DTE
- workflow source
- provider source
- as-of timestamp when available

### Legs table

Each structure should later show a compact legs table with:

- buy / sell
- call / put
- strike
- contracts
- multiplier
- premium assumption when available

### Risk summary

Each surface should later show:

- net debit or net credit
- max profit
- max loss
- breakeven low and/or high
- defined-risk status

### Expected range context

Expected range visualization should appear as context, not as payoff math.

Show:

- status: computed / blocked / omitted
- method
- bounds when available
- reason when blocked or omitted
- explicit copy that expected range does not change expiration payoff math or
  imply execution approval

### 9D design checkpoint - Expected Move visualization

Status:

- `9D1` design checkpoint complete
- `9D2` reusable component plus first Recommendations integration complete
- `9D` closure complete for the current Recommendations scope
- no application code, backend behavior, schema, provider probing, lifecycle
  math, commission math, equity behavior, or payoff math changes are authorized
  by this visualization slice

What 9D should visualize:

- expected lower and upper bounds when `expected_range.status=computed`
- the current / reference underlying price when already available in the
  existing payload, otherwise an explicit `Unavailable` marker
- expiration and DTE from the options structure
- structure breakevens from the research contract or replay payoff preview
- max profit and max loss context as labels, not as a new calculation
- optional payoff-preview sample points only after the operator has already
  run the read-only replay payoff preview
- whether the expected range crosses or overlaps known breakeven / loss-zone
  boundaries, described as context only

What 9D must not do:

- probability of profit
- broker mark-to-market simulation
- expiration settlement
- assignment or exercise modeling
- IV surface modeling
- live execution decisions
- strategy scoring changes
- changes to payoff, lifecycle, commission, or recommendation math

Safest first visualization:

- a compact horizontal range bar, not a full charting surface
- markers for expected lower bound, expected upper bound, current/reference
  price, and breakevens
- muted max-profit / max-loss labels near the structure summary
- a short textual interpretation such as:
  `Expected Range is research context only. It does not change payoff math or
  approve execution.`
- an unavailable state when the range is blocked, omitted, or missing

Recommended placement:

1. Recommendations `Structure risk` surface first, directly under the existing
   Expected Range metric card, because it already has the structure, payoff
   preview, paper lifecycle, provider/source/as-of, and warning context in one
   operator lane.
2. Replay payoff preview area second, only as an optional contextual companion
   to the existing payoff table after a preview has run.
3. Analysis options setup third, as a compact read-only summary if the same
   reusable component stays small.

Do not make the first slice a chart overlay. `WorkflowChart` already supports
price-line overlays, but Expected Range visualization is structure/payoff
context rather than a time-series indicator. A separate compact range bar is
safer, easier to test, and less likely to imply trading-signal precision.

Data dependencies:

- existing `expected_range` fields:
  - `status`
  - `method`
  - `absolute_move`
  - `lower_bound`
  - `upper_bound`
  - `reference_price_type`
  - `snapshot_timestamp`
  - `provenance_notes`
  - `reason`
- existing structure fields:
  - `expiration`
  - `dte`
  - `breakeven_low`
  - `breakeven_high`
  - `max_profit`
  - `max_loss`
- existing replay preview fields, only if already loaded:
  - `breakevens`
  - `payoff_points`
  - `max_profit`
  - `max_loss`

Missing-data behavior:

- missing expected range: render a muted unavailable state with `Expected Range
  unavailable`
- blocked or omitted expected range: show the status plus reason when present
- missing breakevens: omit breakeven markers and show `Breakevens unavailable`
- missing current/reference price: omit the current-price marker and show
  `Reference price unavailable`
- missing expiration or DTE: show `Expiration unavailable` or `DTE unavailable`
  without blocking the component
- SPX/NDX provider limitations: keep the existing provider-plan caveat and
  SPY/QQQ substitute guidance near the data-quality copy, not inside the bar

Required UX copy:

- `Expected Range is research context only.`
- `It does not change payoff math.`
- `It does not approve execution.`
- `Range is based on available provider data and assumptions.`

Recommended implementation slices:

- `9D1` design checkpoint: complete with this section and roadmap alignment
- `9D2` reusable Expected Range visualization component using existing fields
  only, with first Recommendations `Structure risk` integration: complete
- `9D` closure audit for current Recommendations scope: complete
- Analysis integration moved to `10A1`; richer replay placement and
  provider-depth polish remain future work only if explicitly reopened

Phase 10 UX planning:

- `10A1` is complete for the current frontend-only slice:
  `ExpectedRangeVisualization` is reused on Analysis in options mode with
  existing `expected_range`, expiration/DTE, breakeven, source/as-of, and risk
  fields only
- keep the Analysis placement compact and below existing expected-range/source
  context so it reads as research context, not as a new signal or approval
- do not add probability-of-profit, settlement, assignment/exercise,
  lifecycle actions, provider probes, or recommendation scoring changes
- later replay/Orders visualization polish should remain read-only and
  paper-only unless a separate higher-risk phase explicitly changes the
  lifecycle contract

Closure notes:

- computed ranges show lower/upper bounds and breakeven markers
- blocked, omitted, missing, and invalid-number states render safely
- derived range midpoint labeling does not imply an actual current/reference
  price when that price is absent from the payload
- the component stays inside Recommendations `Structure risk` and does not
  broaden or redesign the options page
- no probability, execution-approval, live-trading, or routing language is
  introduced

Recommended test plan for 9D implementation:

- computed expected range with breakeven markers
- blocked expected range reason
- missing expected range fallback
- missing breakeven and missing current/reference price fallbacks
- no probability-of-profit, routing, broker-execution, or execution-approval
  language
- safe rendering for `null`, `undefined`, `NaN`, and `Infinity`

### Payoff preview

Early payoff UX should prefer compact summaries:

- payoff table
- terminal payoff examples
- simple payoff chart concept later if useful

The first UX slice does not require:

- a complex payoff graph editor
- intraday mark-to-market realism

## Warning and caveat system

Options surfaces should later use compact operator warnings for:

- paper-only assumptions
- assignment / exercise caveats
- missing or stale chain data
- wide spread or weak liquidity caveats when detectable
- incomplete legs or unsupported structure type

Warnings should be:

- explicit
- short
- operator-actionable

## Data quality and missing-data states

Required rendering rules:

- missing values render as `Unavailable` or `-`
- blocked states show a reason
- stale data states show source/as-of context
- no raw `null`, `undefined`, `NaN`, or misleading `0`

## Recommended surface evolution

### Recommendations

Continue to emphasize:

- read-only research context first
- structure summary and expected range context
- replay payoff preview stays read-only and non-persisted
- paper option lifecycle actions stay visually separate and explicitly
  paper-only
- commission-per-contract guardrails stay visible where paper lifecycle
  actions appear
- no broker-order or live-routing CTAs

### Replay

Later replay UX should add:

- structure under test
- payoff summary
- blocked reasons
- estimated fee note when available

### Orders

Current paper-lifecycle UX now adds:

- a dedicated `Paper Options Positions` section on Orders
- separate open versus closed paper option lifecycle visibility
- leg summaries plus open/manual-close state copy
- gross/opening/closing/total/net result visibility for closed paper option
  positions
- paper-only labels that stay separate from the existing equity Orders tables
- a source/as-of limitation note explaining that durable paper lifecycle rows
  may not include full provider metadata yet and that this is not a lifecycle
  error

Later Orders maturity can still add:

- leg-aware paper ticket
- expiration status
- richer multi-position workflow actions

## 8E implementation slices

### 8E1 - Core risk summary

Status:

- complete for the current Recommendations options research surface

Implemented now:

- compact risk-summary cards for structure type, net debit/credit, max
  profit/loss, breakevens, expiration / DTE, legs / multiplier, Expected
  Range status, replay-preview status, and paper lifecycle state
- compact lifecycle outcome visibility for gross P&L, opening commissions,
  closing commissions, total commissions, and net P&L after manual close
- warning/caveat copy that keeps Expected Range, replay payoff preview, and
  paper lifecycle in clearly separated roles

Must not change:

- equity workspace behavior

### 8E2 - Warning and data-quality system

Status:

- complete for the current Recommendations options research surface

Implemented now:

- the existing `Structure risk` surface now repeats compact source/as-of
  context for underlying research, chain preview, and Expected Range
  provenance without merging replay preview and paper lifecycle into one lane
- missing source/as-of values render as `Source unavailable` /
  `As-of unavailable`
- data-quality warnings now call out missing chain preview, missing IV /
  Greeks / open interest context, blocked/omitted Expected Range reasons,
  unsupported or incomplete structures, missing expiration/DTE, and SPX/NDX
  provider-plan caveats
- chain-preview copy now explains when reference rows are present but
  quote/liquidity fields such as `last` / `volume` remain unavailable, and it
  explicitly warns when only calls or only puts are returned for the current
  expiry/source
- Expected Range remains first-class research context while staying explicit
  that it does not modify payoff math or imply execution approval

Must not change:

- provider-readiness semantics

### 8E3 - Guided workflow clarity

Status:

- complete for the current Recommendations options research surface

Implemented now:

- a compact stepper now makes the five-stage flow explicit:
  review structure -> preview payoff -> save paper position -> manually close
  -> review paper close result
- replay payoff preview and paper lifecycle now use clearer operator wording:
  replay preview is read-only/non-persisted, while paper lifecycle creates
  persisted paper-only records and does not place a broker order
- the final workflow step now makes it explicit that gross/commission/net
  outcome fields appear only after manual paper close and belong to the saved
  paper options lifecycle
- manual close inputs now explain what `exit premium` means, include a
  per-leg example plus long/short direction hint, and restate that premium
  uses `x100` while commission does not
- successful manual close results now render through a clearer result card
  that states no broker order was sent
- provider/warning detail is now progressively disclosed so the workflow is
  easier to scan without removing safety copy

Must not change:

- replay/order enablement boundaries

## Acceptance criteria

8E is complete when:

- supported options surfaces present risk data coherently
- paper-only and non-execution caveats are visible
- missing data is safe and explicit
- provider/source/as-of context is present where available
- the current `Structure risk` layer remains aligned with replay-preview and
  paper-lifecycle boundaries rather than collapsing them into one implied
  execution flow

Current closure status:

- `8E` is complete for the current Recommendations options surface only
- `9C1` is complete for Analysis, Orders durable paper-options rows, and
  Provider Health copy using existing payload fields only
- `9C` is complete for the current provider/source/as-of parity scope
- future provider-depth, new options surfaces, or live-probe work should reopen
  parity checks in their own phase
- `9D1` design checkpoint is complete for advanced Expected Move visualization
- `9D2` reusable component plus first Recommendations integration is complete
- `9D` is closed for the current Recommendations Expected Range visualization
  scope
- Phase 9 is closed for the current options operator parity,
  provider/source/as-of, and Recommendations Expected Range visualization
  scope
- Phase 10 is open for planning and safe polish only; `10A1` optional Analysis
  Expected Range visualization is complete for the current frontend-only slice
- deeper replay/provider visualization remains deferred
- `8F` is now complete for the current scoped paper-first options capability
- full live-routing, settlement, assignment/exercise, and broader Orders
  parity remain explicitly outside this scope

8E is not complete if:

- a surface still hides max loss or breakevens
- stale/missing data looks healthy
- options UX implies live routing or broker realism

## Rollback principle

Any 8E work should be removable by hiding options-specific view components
without disturbing the equity workflow surfaces.
