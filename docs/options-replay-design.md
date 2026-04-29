# Phase 8C Options Replay Design

Last updated: 2026-04-29

## Purpose

This document defines `8C`: read-only, non-persisted options replay preview
for defined-risk structures.

It is planning only. It does not authorize:

- schema changes
- migrations
- staged options orders
- options positions or trades
- live routing

## What "options replay" means in 8C

For Phase 8C, options replay means:

- a read-only replay preview
- one supported structure at a time
- deterministic payoff-at-expiration review first
- paper-only and research-only operator feedback
- explicit blocked reasons when required data is incomplete

Phase 8C does not yet mean:

- equity-style replay persistence
- fill simulation parity with a broker
- intraday mark-to-market valuation parity
- assignment or exercise automation
- options order enablement

## Supported first structures

Implementation order:

1. vertical debit spreads
2. iron condor on the same leg/payoff helper foundation
3. optional long call / long put primitives only if they simplify shared math

Blocked or deferred:

- naked short call
- naked short put
- covered call replay that depends on inventory and assignment modeling

## Structure assumptions

Replay preview should rely on structure data already surfaced in Analysis /
Recommendations:

- underlying symbol
- structure type
- expiration date
- DTE
- per-leg right / strike / action
- contracts count where available
- premium or net debit / credit assumption
- max profit / max loss when already explicit
- breakevens when already explicit

Expected range is contextual only:

- useful for research framing
- not a substitute for payoff math
- allowed to be computed, blocked, or omitted

## Required data for a valid preview

Required:

- `market_mode=options`
- supported structure type
- underlying price history from the same workflow source as the research setup
- expiration / DTE
- leg definitions with strike / right / action
- premium assumption at the structure or leg level

Preferred but not required in the first slice:

- chain preview rows
- provider symbols
- implied volatility snapshots
- expected range

Missing-data behavior:

- missing or partial legs -> block preview with explicit reason
- missing expiration -> block preview
- missing premium / net debit / net credit -> block preview
- missing chain preview -> allow preview if structure math is otherwise valid
- blocked or omitted expected range -> preview may still proceed, with reason

## Replay math scope

Initial 8C replay math should cover:

- contract multiplier, default `100`
- leg-level payoff at expiration
- structure-level net debit or net credit
- max profit
- max loss
- breakevens
- expiration payoff table
- blocked or rejected reasons

`commission_per_contract` handling in 8C:

- may be shown as an estimate only when contracts are explicit enough to do so
  deterministically
- should not be required to ship the first replay preview slice
- should not turn 8C into an options paper-lifecycle implementation

Mark-to-market and Greeks:

- deferred
- do not approximate unless provider-depth work later makes the assumptions
  trustworthy

## Separation from equity replay

Current equity replay must remain untouched.

Hard rules:

- do not route options replay through `ReplayEngine`
- do not route options replay through `RecommendationService.generate()`
- do not fabricate equity `OrderIntent`, `OrderRecord`, or `FillRecord`
- do not persist options replay in equity-shaped `replay_runs` rows in the
  first slice

Recommended contract direction:

- keep current equity replay request/response contracts unchanged
- introduce a dedicated read-only options replay preview contract
- keep UI routing and CTAs mode-aware

## Recommended API / contract direction

Safest first implementation:

- add a dedicated read-only preview route or mode-specific response branch
- return a non-persisted preview payload
- keep current replay DB rows and engine behavior untouched

Suggested response shape:

```json
{
  "market_mode": "options",
  "preview_mode": "read_only_expiration_payoff",
  "workflow_source": "provider|fallback",
  "provider_source": "polygon|fallback",
  "underlying_symbol": "SPY",
  "structure_type": "bull_call_debit_spread",
  "expiration_date": "2026-05-15",
  "days_to_expiration": 16,
  "status": "ready|blocked|unsupported",
  "blocked_reasons": [],
  "legs": [
    {
      "action": "buy",
      "right": "call",
      "strike": 520.0,
      "contracts": 1,
      "multiplier": 100
    }
  ],
  "entry_assumptions": {
    "net_debit": 2.15,
    "net_credit": null,
    "premium_source": "analysis_setup_payload",
    "commission_model": "deferred|estimated_only"
  },
  "payoff_summary": {
    "max_profit": 285.0,
    "max_loss": 215.0,
    "breakeven_low": null,
    "breakeven_high": 522.15
  },
  "expiration_scenarios": [
    {
      "underlying_price": 515.0,
      "gross_payoff": -215.0,
      "net_payoff": null
    }
  ],
  "expected_range": {
    "status": "computed|blocked|omitted",
    "method": "iv_move",
    "lower_bound": 512.0,
    "upper_bound": 528.0,
    "reason": null
  },
  "operator_notes": [
    "Options replay preview only. Not execution support."
  ]
}
```

Payload rules:

- missing values render as `null` in the API only when the frontend can safely
  convert them to `Unavailable` or `-`
- do not backfill missing values with fake zeros
- blocked states should contain deterministic human-readable reasons

## UI plan for 8C

The Replay workspace should later show:

- underlying symbol
- structure type
- expiration / DTE
- legs table
- entry debit / credit assumption
- estimated commission note when available
- max profit / max loss
- breakevens
- expiration payoff summary
- blocked or unsupported reasons
- paper-only / research-only disclaimer

The Replay workspace should not show in 8C:

- stage order now
- order routing language
- equity-style fill timeline pretending to be broker-realistic

## 8C implementation slices

### 8C1 - Planning and contracts

Complete when:

- mode-specific options replay boundaries are documented
- dedicated request/response direction is agreed

Must not change:

- equity replay behavior

Rollback:

- docs-only; no runtime rollback needed

### 8C2 - Pure payoff math helper

Status:

- complete

Complete when:

- deterministic payoff helpers exist for supported structures
- unit tests prove max profit/loss, breakevens, and expiration scenarios

Must not change:

- replay routes
- replay persistence
- equity replay engine

Rollback:

- remove helper module and tests without touching equity replay

### 8C3 - Read-only replay preview contract

Status:

- complete

Complete when:

- a dedicated preview response exists for options mode
- preview can return ready, blocked, and unsupported states
- no replay DB rows are created

Must not change:

- current equity replay request/response behavior

Rollback:

- disable the options preview route or mode branch without touching equity
  replay

### 8C4 - Operator UI preview

Complete when:

- operators can inspect the replay preview safely
- missing values render safely
- order/staging CTAs remain suppressed

Must not change:

- replay order-enablement behavior for equities

Rollback:

- hide the options replay preview UI behind mode gating

### 8C5 - Tests and docs closure

Complete when:

- backend math tests exist
- frontend rendering tests exist
- equity replay regression tests pass
- roadmap/docs reflect the actual shipped 8C boundary

Must not change:

- the 8D lifecycle scope

Rollback:

- remove or tighten the 8C status note if implementation proves too broad

## Required tests

Backend:

- payoff math for vertical debit spreads
- payoff math for iron condor
- blocked replay for missing premium
- blocked replay for missing expiration
- blocked replay for incomplete legs
- unsupported structure rejection
- equity replay regression anchors

Frontend:

- replay preview renders supported structure summary
- blocked reasons render clearly
- expected range stays contextual
- missing values render as `Unavailable` or `-`
- options mode suppresses staging/order CTAs

## Current implementation note

Phase 8C2 and 8C3 are now implemented in:

- `src/macmarket_trader/options/payoff.py`
- `src/macmarket_trader/options/replay_preview.py`
- `src/macmarket_trader/api/routes/admin.py`
- `tests/test_options_payoff.py`
- `tests/test_options_replay_preview.py`

Implemented scope:

- long call and long put primitives
- short-leg payoff primitives for internal math use
- structure analysis for vertical debit spreads
- structure analysis for iron condor
- explicit blocked results for unsupported or invalid inputs, including naked
  short single-leg structures
- a dedicated read-only options replay preview contract at
  `POST /user/options/replay-preview`
- safe `ready`, `blocked`, and `unsupported` response states
- deterministic generated payoff grids when underlying prices are omitted
- no replay DB rows, orders, or recommendations created by preview requests

Still deferred:

- any replay UI
- any persistence
- any commission application

## Recommended next implementation slice

Proceed with `8C4.1` next:

- add an operator-facing replay preview UI for options mode
- consume the existing read-only preview contract without adding persistence
- keep order, staging, and lifecycle CTAs suppressed
- keep equity replay untouched

That is the safest next step because the core payoff math and backend preview
contract are now proven, and the remaining work is isolated UI inspection.
