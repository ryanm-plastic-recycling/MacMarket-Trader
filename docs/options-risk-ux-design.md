# Phase 8E Options Risk UX Design

Last updated: 2026-04-29

## Purpose

This document defines the operator-facing risk UX for the current
Recommendations options surface and its planned follow-on slices.

The current Recommendations options surface now satisfies `8E1` through `8E3`
plus closure review for the scoped risk/operator UX pass. It does not require
a full charting implementation in the first slice, and later options surfaces
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
- broader Orders dashboard parity remains deferred

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

Expected range should later appear as context, not as payoff math.

Show:

- status: computed / blocked / omitted
- method
- bounds when available
- reason when blocked or omitted
- explicit copy that expected range does not change expiration payoff math or
  imply execution approval

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

Later paper-lifecycle UX should add:

- leg-aware paper ticket
- open/close summaries
- gross and net P&L
- expiration status
- durable options position/trade listing once backend read APIs are added

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
- broader provider/source/as-of parity across other options surfaces remains
  deferred
- advanced Expected Move visualization remains deferred
- `8F` remains the next full Phase 8 closure pass

8E is not complete if:

- a surface still hides max loss or breakevens
- stale/missing data looks healthy
- options UX implies live routing or broker realism

## Rollback principle

Any 8E work should be removable by hiding options-specific view components
without disturbing the equity workflow surfaces.
