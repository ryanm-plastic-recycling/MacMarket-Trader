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

Required later for options paper lifecycle:

- structure open lifecycle tests
- structure close lifecycle tests
- gross versus net realized P&L tests
- `commission_per_contract` application tests
- debit versus credit handling tests
- defined-risk validation tests
- blocked naked-short tests
- blocked unsupported assignment/exercise automation tests

Equity regression tests required alongside 8D:

- current paper order lifecycle tests
- current close/reopen tests
- current fee-preview tests

## 8D frontend tests

Required later for options paper lifecycle UI:

- leg-aware paper ticket rendering
- debit/credit display
- commission display
- gross/net P&L display
- expiration-status display
- paper-only warning display

## 8E frontend tests

Required later for operator risk UX:

- risk summary renders max profit/loss and breakevens
- warnings render for paper-only and missing-data states
- provider/source/as-of labels render when available
- stale or unavailable data does not look healthy

## Route and CTA safety tests

Phase 8 should continue to prove:

- options mode does not call queue/promote routes in 8B or 8C
- options mode does not expose order/staging CTAs before 8D
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

### 8E gate

- risk UX tests pass
- provider/source labeling tests pass
- CTA suppression boundaries remain correct

### 8F gate

- supported defined-risk options flow is testable end to end for the intended
  paper-only scope
- deferred items remain documented rather than implied complete

## Suggested future test file direction

Backend:

- `tests/test_options_payoff_math.py`
- `tests/test_options_replay_preview.py`
- `tests/test_options_paper_schema.py`
- `tests/test_options_paper_lifecycle.py`

Frontend:

- options replay preview tests near the Replay workspace code
- options lifecycle/risk component tests near their feature components

Keep these additions mode-specific and avoid rewriting current equity tests
unless a true regression requires it.
