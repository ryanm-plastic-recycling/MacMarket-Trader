# Phase 8D Options Paper Lifecycle Design

Last updated: 2026-04-29

## Purpose

This document defines the future `8D` options paper lifecycle.

It is planning only. It does not authorize:

- schema changes
- migrations
- options order staging
- live routing
- assignment or exercise automation

## Why 8D must stay separate from equities

The current paper lifecycle is equity-centric:

- one symbol
- one side
- one quantity
- one average entry
- one close price

Options lifecycle needs different semantics:

- structure-level identity
- leg-level identity
- debit or credit handling
- contract multiplier math
- multi-leg open / close state
- per-contract commission

The safest future implementation path is a dedicated options branch, not a
hidden extension of current equity order models.

## Future lifecycle model

### Option contract identity

Each contract should later carry:

- underlying symbol
- expiration date
- strike
- call / put
- contracts quantity
- multiplier, default `100`
- provider symbol when available

### Option leg identity

Each leg should later carry:

- leg index
- action: `buy` or `sell`
- right: `call` or `put`
- strike
- contracts
- multiplier
- open premium
- close premium

### Structure identity

Each paper structure should later carry:

- market mode `options`
- structure type
- underlying symbol
- expiration date
- DTE at open
- legs
- net opening debit or credit
- max profit
- max loss
- breakevens
- workflow source / provider source
- lineage back to setup / recommendation / replay when applicable

## Opening lifecycle

Opening a supported options paper structure should later require:

- supported defined-risk structure type
- complete leg definitions
- explicit premium or net debit / credit assumptions
- explicit quantity / contracts assumptions
- operator-visible paper-only execution notes

Opening outputs should later include:

- structure status `open`
- per-leg opening summary
- total opening debit or credit
- estimated or applied opening commission
- gross opening cash impact
- net opening cash impact

## Closing lifecycle

Closing a supported options paper structure should later require:

- inverse action for each leg
- close premium assumptions
- close timestamp or expiration-settlement assumption
- paper-only close notes

Closing outputs should later include:

- per-leg close summary
- structure gross realized P&L
- structure net realized P&L
- total commission applied
- terminal status such as:
  - closed manually
  - expired worthless
  - settled at expiration

## Commission and P&L rules

Future 8D should apply `commission_per_contract` explicitly.

Planning math:

- long leg gross P&L:
  `(close_premium - open_premium) * contracts * multiplier`
- short leg gross P&L:
  `(open_premium - close_premium) * contracts * multiplier`
- structure gross P&L:
  sum of leg gross P&L
- total commission:
  `(open_contracts + close_contracts) * commission_per_contract`
- structure net P&L:
  `gross_pnl - total_commission`

Credit/debit rules:

- opening debit structures reduce cash at open
- opening credit structures increase cash at open
- gross/net realized P&L must still be computed from leg outcomes, not from
  a loosely named cash field

## Early-scope constraints

Supported first:

- vertical debit spreads
- iron condor after replay math is proven

Explicitly deferred:

- naked short options
- partial fills in the earliest lifecycle slice
- assignment / exercise automation
- covered calls that require inventory awareness
- margin modeling

## Likely persistence direction

No schema work is authorized yet. When Phase 8D implementation begins, the
safest checkpoint is `8D1`: decide whether to use dedicated options tables or a
generic multi-asset contract that still keeps option legs explicit.

Planning bias:

- prefer an options-specific persistence branch over stretching current equity
  `OrderModel`, `PaperPositionModel`, and `PaperTradeModel`
- preserve lineage compatibility with current workflow URLs and audit concepts
- keep leg detail queryable and auditable

## 8D implementation slices

### 8D1 - Schema and lifecycle design checkpoint

Complete when:

- the persistence direction is chosen and documented
- migration scope is known but not yet mixed with unrelated feature work

Must not change:

- current equity paper lifecycle

Rollback:

- revert to docs-only plan; no runtime behavior affected

### 8D2 - Paper option order contract

Complete when:

- a dedicated options paper-order contract exists
- structure and leg identity are explicit
- staging semantics remain paper-only

Must not change:

- equity order staging behavior

Rollback:

- disable the options order contract path behind market mode

### 8D3 - Structure open/close lifecycle foundation

Complete when:

- supported structures can open and close in paper mode
- lifecycle remains structure-aware and leg-aware
- partial fills stay deferred unless explicitly approved

Must not change:

- equity fill simulation behavior

Rollback:

- remove the options open/close path without touching equities

### 8D4 - `commission_per_contract` application

Complete when:

- contract-level commission is applied deterministically
- gross versus net P&L remains explicit
- UI labels explain paper-only assumptions

Must not change:

- current equity commission logic

Rollback:

- feature-flag or disable only the options commission path

### 8D5 - Tests and docs closure

Complete when:

- lifecycle math tests pass
- frontend paper-lifecycle rendering tests pass
- equity paper workflow regressions pass
- roadmap/docs reflect actual supported structures only

## UI and operator implications

Later 8D UI should show:

- structure summary
- legs table
- debit / credit
- estimated and applied commissions
- gross and net realized P&L
- expiration status
- paper-only assignment/exercise caveat

It should not imply:

- live routing
- real broker fill realism
- hidden margin support

## Rollback principle

Every 8D code slice should be removable by market-mode gating without forcing
changes into current equity orders, positions, or trades.
