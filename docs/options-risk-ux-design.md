# Phase 8E Options Risk UX Design

Last updated: 2026-04-29

## Purpose

This document defines the operator-facing risk UX for future options support.

It is planning only. It does not require a full charting implementation in the
first slice.

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
- no execution CTAs until later phases

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

## 8E implementation slices

### 8E1 - Core risk summary

Complete when:

- legs, debit/credit, max profit/loss, breakevens, and DTE are visible on
  supported options surfaces

Must not change:

- equity workspace behavior

### 8E2 - Warning and data-quality system

Complete when:

- options surfaces show paper-only, data-quality, and assignment caveats

Must not change:

- provider-readiness semantics

### 8E3 - Payoff visualization polish

Complete when:

- operators can inspect payoff examples safely without implying execution
  readiness

Must not change:

- replay/order enablement boundaries

## Acceptance criteria

8E is complete when:

- supported options surfaces present risk data coherently
- paper-only and non-execution caveats are visible
- missing data is safe and explicit
- provider/source/as-of context is present where available

8E is not complete if:

- a surface still hides max loss or breakevens
- stale/missing data looks healthy
- options UX implies live routing or broker realism

## Rollback principle

Any 8E work should be removable by hiding options-specific view components
without disturbing the equity workflow surfaces.
