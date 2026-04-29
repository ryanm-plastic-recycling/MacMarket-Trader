# Phase 8 Options Architecture Plan

Last updated: 2026-04-29

## Purpose

This document defines the Phase 8 options architecture for MacMarket-Trader.
It is a planning artifact only. It does not authorize live trading, brokerage
routing, schema changes, or execution implementation.

Phase 8 must preserve the current product center and paper-only posture:

- Analysis / Strategy Workbench remains the primary setup surface
- Recommendations remains the flagship review surface
- Replay validates before paper execution
- Orders remains paper-only and auditable

## Current repo anchors

The current repository already provides a few useful foundations:

- `README.md` defines options as planned research-preview / paper-first later
- `TradeRecommendation.market_mode` already exists and defaults to `equities`
- `domain/schemas.py` already includes:
  - `InstrumentIdentity`
  - `OptionContractContext`
  - `OptionStructureLeg`
  - `OptionStructureContext`
  - `ExpectedRange`
- `admin.py` already contains `_build_options_expected_range(...)`
- `market_data.py` already contains Polygon `options_chain_preview(...)`
- `app_users.commission_per_contract` already exists, but is not yet applied

Those anchors should be extended deliberately rather than replaced.

## Design goals

- Keep options mode explicitly separate from equity execution-prep logic
- Preserve deterministic, auditable, paper-first behavior
- Prefer defined-risk structures first
- Keep provider readiness separate from execution enablement
- Ship in small slices that can be tested without destabilizing current equity
  workflows

## Non-goals for initial Phase 8 implementation

- live brokerage routing
- options live execution
- naked short options
- automated assignment / exercise handling
- margin modeling beyond explicitly modeled defined-risk structures
- cross-contaminating current equity scoring or paper-position logic

## 1. Option instrument model

Phase 8 should treat an option contract as a first-class instrument, not as an
equity symbol with extra text fields.

Recommended normalized contract identity:

- `market_mode`: `options`
- `instrument_type`: future explicit option-contract type
- `underlying_symbol`
- `expiration_date`
- `days_to_expiration`
- `strike`
- `option_right`: `call` or `put`
- `contract_multiplier`: default `100`
- `provider_symbol`: provider-native contract symbol when available
- `occ_symbol`: OCC-style symbol when available

Recommended optional market fields for later provider-backed use:

- `bid`
- `ask`
- `mark`
- `last`
- `implied_volatility`
- `delta`
- `gamma`
- `theta`
- `vega`
- `open_interest`
- `volume`

Recommended planning rule:

- `OptionContractContext` should remain the starting point, but later Phase 8
  implementation will likely need one normalized contract payload that can be
  used consistently by recommendations, replay, and paper orders.

## 2. Options paper order lifecycle

The current paper order lifecycle is equity-centric:

- one symbol
- one side
- one share quantity
- one average entry
- one close price

Options paper lifecycle must become leg-aware.

### Open lifecycle requirements

For each leg:

- open action: `buy` or `sell`
- contracts quantity
- premium paid or received
- contract multiplier
- opening commission based on `commission_per_contract`

For the overall structure:

- net opening debit or credit
- opening timestamp
- source recommendation / replay lineage
- paper-only fill assumption source

### Close lifecycle requirements

For each leg:

- close action is the inverse of open action
- close premium
- closing commission based on `commission_per_contract`

For the overall structure:

- net closing debit or credit
- gross realized P&L
- net realized P&L after commissions
- close reason
- expiry-aware terminal status

### P&L modeling

Recommended contract-level math:

- long leg gross P&L:
  `(close_premium - open_premium) * contracts * multiplier`
- short leg gross P&L:
  `(open_premium - close_premium) * contracts * multiplier`
- per-leg net P&L:
  `gross_leg_pnl - ((open_contracts + close_contracts) * commission_per_contract)`
- structure gross P&L:
  sum of leg gross P&L
- structure net P&L:
  structure gross P&L minus total commission

Recommended early execution assumption:

- paper-only fills use explicit modeled premiums from a safe source
- no claim of live fill realism until provider-backed options quotes and replay
  parity exist

### Paper-only assignment / exercise caveat

Early options paper trading should not automate assignment or exercise.
Instead:

- long options may be modeled as closed before expiry or settled by modeled
  expiration payoff
- short defined-risk spreads may be modeled to expiration payoff only
- naked assignment risk is out of scope until explicitly designed later

## 3. Multi-leg strategy representation

Phase 8 should support multi-leg structures explicitly, especially Iron
Condor.

Recommended structure payload:

- `strategy_id`
- `structure_type`
- `underlying_symbol`
- `expiration_date`
- `days_to_expiration`
- `legs[]`
- `net_open_debit_credit`
- `net_close_debit_credit`
- `max_profit`
- `max_loss`
- `breakeven_low`
- `breakeven_high`
- `defined_risk`
- `assignment_caveat`
- `paper_execution_notes`

Recommended leg payload:

- `leg_index`
- `action`: `buy` or `sell`
- `option_right`: `call` or `put`
- `strike`
- `contracts`
- `multiplier`
- `provider_symbol` or normalized contract id
- `open_premium`
- `close_premium`

### Iron Condor representation

Iron Condor should be represented as four explicit legs:

- short put
- long put wing
- short call
- long call wing

Required deterministic structure outputs:

- net credit received
- wing width
- max profit
- max loss
- lower breakeven
- upper breakeven
- expiration date
- expected-range context when available

Recommended early scope rule:

- defined-risk structures only
- no naked short calls
- no naked short puts

## 4. Replay and recommendation integration

Options implementation must not contaminate current equity scoring or paper
workflow semantics.

### Separation rule

- keep `market_mode=equities` and `market_mode=options` explicitly separate
- do not reuse equity share-sizing and stop-distance logic for options
- keep current equity recommendation scoring unchanged unless an equity defect
  requires separate work

### Recommendation integration plan

Options recommendations should later carry option-aware payloads in addition to
the existing recommendation lineage fields.

Later option-aware recommendation payloads will need:

- normalized option contract or structure identity
- premium / credit / debit context
- max profit / max loss
- breakevens
- expiration / DTE
- expected range method and status
- liquidity-quality notes
- provider source and fallback labeling

### Replay integration plan

Options replay should later operate as a separate mode:

- replay request carries `market_mode=options`
- replay summary remains mode-aware and paper-only
- stageable candidate logic becomes option-aware instead of assuming one equity
  order intent
- replay steps should carry structure-level state, not just equity-style order
  count and open notional

### Expected range usage

Expected range is useful in options mode, but should remain contextual:

- support structure selection or strike placement
- support Iron Condor wing / short-strike checks
- remain separate from breakeven and payoff math
- remain provenance-tagged via `ExpectedRange`

### Recommendation surfaces that will later need option-aware payloads

- Analysis setup response
- recommendations queue
- recommendation promote response
- recommendation detail payload
- replay run create/list/detail/steps
- staged order response
- orders blotter
- paper positions / trades history

## 5. UI / UX plan

Options operator UX should stay compact and desk-like, not retail-broker-like.

### Recommendations

Options candidates should later show:

- underlying
- structure type
- expiration / DTE
- leg summary
- credit or debit
- max profit
- max loss
- breakevens
- expected range method / status
- provider source / fallback status

### Replay

Replay should later show:

- structure under test
- per-step approval / rejection context
- projected payoff or realized modeled outcome
- estimated contract commissions
- explicit paper-only assumptions

### Orders

Paper order tickets should later show:

- legs table
- buy/sell per leg
- contracts per leg
- premium per leg
- net credit or debit
- estimated opening commission
- estimated closing commission
- max profit
- max loss
- breakevens
- expiration risk
- paper-only assignment / exercise caveat

### Rendering rules for unavailable data

Unavailable option data must render safely as `Unavailable`, not:

- `0`
- `NaN`
- `undefined`
- `null`

Examples:

- missing mark
- missing IV
- missing OI
- missing projected net
- unavailable expected range

## 6. Provider and data assumptions

### What already exists

- Polygon options chain preview already exists in `market_data.py`
- current Polygon preview returns nearest-expiry contract reference rows only
- current preview does not provide execution parity, greeks, or mark modeling
- Alpaca paper broker scaffold exists separately
- provider-health wording already distinguishes readiness from live health

### Current limitations

- current Polygon chain preview is suitable for early read-only research
  scaffolding, not full replay/order parity
- current Alpaca market-data scaffold is equities-oriented
- current Alpaca paper broker scaffold should not be used as a dependency for
  initial Phase 8 implementation

### Data likely needed later for options parity

- provider contract identifiers
- bid / ask / mark or safe modeled mid
- volume and open interest
- implied volatility
- Greeks when available
- expiration calendar handling
- contract-level quote timestamps

### Provider-readiness policy

- provider readiness stays separate from execution enablement
- Alpaca readiness remains paper/provider-readiness only until a later explicit
  execution phase
- FRED and news readiness remain supporting workflow context only and do not
  imply options execution support

## 7. Safety and guardrails

- paper-only
- no live routing
- no brokerage credential entry screens
- no naked short options in early implementation
- defined-risk structures first
- no assignment / exercise automation
- no margin assumptions unless explicitly modeled later
- no hidden fallback data mixing across recommendation / replay / orders
- no options implementation that silently reuses equity sizing or close math

## 8. Proposed implementation slices

### Phase 8A — Architecture and contract planning

Status in this pass:

- docs-only architecture plan
- no schema changes
- no migrations
- no application code changes

### Phase 8B — Read-only options research contracts

Safest first implementation slice after approval.

Scope:

- introduce explicit option/structure payload contracts in the API layer
- wire `market_mode=options` through Analysis and Recommendations research
  surfaces only
- use existing options chain preview and expected-range scaffolding where
  available
- do not stage orders
- do not persist options positions or trades yet

Why first:

- smallest behavior surface
- no order lifecycle risk
- no fill simulation changes
- no schema/migration pressure on the first code slice
- protects current equity workflow credibility

### Phase 8C — Options replay for defined-risk structures

Scope:

- add option-aware replay requests and summaries
- keep replay mode-separate from equity replay
- support defined-risk structures first
- include contract commission estimates
- no live execution

Recommended initial boundary:

- replay one structure at a time
- iron condor and simple verticals before broader strategy coverage

### Phase 8D — Options paper order and position lifecycle

Scope:

- persist option structure orders, fills, open positions, and closed trades
- apply `commission_per_contract`
- store gross and net realized P&L at structure and leg summary level
- keep assignment / exercise modeled, not automated

Recommended early boundary:

- defined-risk structures only
- one position per structure lineage
- no naked short exposure

### Phase 8E — Operator risk and lifecycle UX hardening

Scope:

- options-aware Orders and Replay surfaces
- max profit / loss and breakeven display
- expiration risk warnings
- explicit unavailable-state handling
- paper-only caveat copy

### Phase 8F — Phase 8 closure criteria

Scope:

- options fee parity confirmed for supported structures
- replay and paper-order parity confirmed within options mode
- provider-source labeling confirmed across recommendations, replay, and orders
- tests cover supported options flows end to end

## Safest first implementation slice after approval

Proceed with Phase 8B first:

- read-only options research contracts in Analysis and Recommendations
- use current chain preview plus explicit expected-range metadata where
  available
- keep Orders, replay persistence, and schema changes out of the first code
  slice

That sequence keeps the first approved implementation small, reviewable, and
unlikely to destabilize the current equity paper-trading workflow.
