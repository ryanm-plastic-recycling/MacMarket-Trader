# Phase 8D Options Paper Lifecycle Design

Last updated: 2026-04-29

## Purpose

This document defines the `8D` design checkpoint, schema foundation,
repository/service contracts, and current runtime boundary for options paper
lifecycle support.

`8D1` design, `8D2` schema foundation, `8D3` repository/service contracts,
`8D4` open paper option structure behavior, and `8D5` manual close paper
option structure behavior are now implemented. The dedicated options
persistence branch exists and now authorizes supported defined-risk
structures to open and close manually through options-specific paper-only
backend paths. It still does not authorize:

- options order staging
- expiration settlement behavior
- live routing
- brokerage execution
- automatic assignment or exercise handling

## Current repo anchors

The current paper lifecycle is intentionally equity-centric:

- `OrderIntent` / `OrderRecord` / `FillRecord` in
  `src/macmarket_trader/domain/schemas.py`
- `OrderModel`, `FillModel`, `PaperPositionModel`, and `PaperTradeModel` in
  `src/macmarket_trader/domain/models.py`
- `PaperPortfolioRepository.upsert_position_on_fill(...)`,
  `create_trade(...)`, and `close_position(...)` in
  `src/macmarket_trader/storage/repositories.py`
- `/user/orders`, `/user/orders/{order_id}/close`,
  `/user/paper-positions/{position_id}/close`, and
  `/user/paper-trades/{trade_id}/reopen` in
  `src/macmarket_trader/api/routes/admin.py`

Those contracts assume:

- one symbol
- one side
- one quantity
- one average entry
- one close event
- one realized trade row per close

That shape is not suitable for multi-leg options structures without forcing
equity semantics onto options.

## 8D boundary

`8D` means future support for paper options structures without changing the
current equity paper lifecycle.

Planned `8D` scope:

- option contract identity
- option leg identity
- multi-leg paper order intent
- paper fill assumptions for supported structures
- open option structure lifecycle
- close option structure lifecycle
- realized gross and net P&L
- `commission_per_contract` application
- auditable lineage back to research and replay when available

Still out of scope for the first lifecycle pass:

- live routing
- real brokerage execution
- automatic assignment or exercise handling
- naked short options
- margin assumptions unless explicitly modeled later
- partial fills unless explicitly approved in a later slice

## Lifecycle boundaries

### Option contract identity

Each future option contract record should carry:

- underlying symbol
- expiration date
- strike
- right: `call` or `put`
- contracts quantity
- multiplier, default `100`
- provider symbol or OCC-style symbol when available

### Option leg identity

Each leg should carry:

- structure-local leg index
- action: `buy` or `sell`
- right: `call` or `put`
- strike
- contracts
- multiplier
- open premium
- close premium when closed
- optional operator label

### Structure identity

Each paper options structure should carry:

- `market_mode=options`
- structure type
- underlying symbol
- expiration and DTE at open
- normalized leg snapshots
- net opening debit or credit
- max profit and max loss when known
- breakevens when known
- workflow source and provider source
- lineage back to analysis / recommendation / replay preview when applicable

### Open lifecycle

Future open requests should require:

- supported structure type
- complete leg definitions
- explicit contracts quantity assumptions
- explicit premium or net debit/credit assumptions
- defined-risk validation before persistence
- operator-visible paper-only caveats

Open results should later include:

- structure status `open`
- per-leg opening snapshot
- gross opening cash impact
- estimated or applied opening commission
- net opening cash impact

### Close lifecycle

Current first-pass close support now includes:

- manual close with per-leg close premiums

Still deferred for later close work:

- deterministic expiration settlement with an underlying settlement price

Current close results include:

- per-leg close snapshot
- structure gross realized P&L
- `total_commissions=null` until `8D6`
- `net_pnl=null` until `8D6`
- terminal structure status `closed` with trade `settlement_mode=manual_close`

## Schema approach comparison

Two realistic persistence approaches exist for `8D`.

### Approach A — Extend current equity tables

Shape:

- add `market_mode`, `instrument_type`, and options fields to current
  `orders`, `fills`, `paper_positions`, and `paper_trades`
- store multi-leg detail either as JSON blobs or bolt-on child tables

Evaluation:

| Topic | Assessment |
|---|---|
| Migration complexity | Medium initially, then high as more option-specific exceptions accumulate |
| Equity contamination risk | High |
| Query/reporting complexity | High because one-table code paths become heavily branched |
| Ease of close lifecycle | Poor for multi-leg close, reopen, and per-leg commission accounting |
| Testability | Weak because every lifecycle test becomes mode-branch-heavy |
| Rollback risk | High because failed options work would be tangled into equity tables and routes |

Main problem:

- the current equity tables encode one-symbol/one-side/one-quantity semantics,
  so extending them would either hide leg detail inside JSON or force
  option-specific nullable columns into every equity flow

### Approach B — Separate options-specific persistence branch

Shape:

- keep equity tables unchanged
- add dedicated options structure and leg tables in `8D2`
- use structure-header plus leg-detail tables instead of trying to coerce
  legs into the current equity row shape

Recommended future table direction:

- `paper_option_orders`
- `paper_option_order_legs`
- `paper_option_positions`
- `paper_option_position_legs`
- `paper_option_trades`
- `paper_option_trade_legs`

Evaluation:

| Topic | Assessment |
|---|---|
| Migration complexity | Medium-high, but contained and explicit |
| Equity contamination risk | Low |
| Query/reporting complexity | Medium; cross-mode reporting should happen in serializers or read models, not shared write tables |
| Ease of close lifecycle | Strong because structures and legs remain first-class |
| Testability | Strong because options lifecycle tests can stay mode-specific |
| Rollback risk | Low-medium because the options branch can be disabled by market mode |

### Recommendation

Recommend **Approach B: separate options-specific persistence**.

Reason:

- it preserves the current equity lifecycle untouched
- it keeps leg detail auditable and queryable
- it makes close math and commission application deterministic
- it makes rollback safer if an early options lifecycle slice proves too broad

Design bias:

- prefer separate write tables plus shared serializers
- do not unify equities and options at the DB write-path level yet
- if consolidated reporting is later needed, build a shared read model rather
  than a shared persistence contract

## 8D2 schema foundation implemented now

The dedicated options persistence branch now exists in ORM metadata and Alembic
revision `20260429_0007`.

Implemented table family:

- `paper_option_orders`
- `paper_option_order_legs`
- `paper_option_positions`
- `paper_option_position_legs`
- `paper_option_trades`
- `paper_option_trade_legs`

Implemented schema traits:

- separate header/leg tables for orders, positions, and trades
- user scoping via `app_user_id`
- structure identity via `underlying_symbol`, `structure_type`, and
  `expiration`
- JSON `breakevens` storage on header rows
- `execution_enabled=false` default on option paper orders
- leg defaults for `quantity=1` and `multiplier=100`
- dedicated parent-FK, user, symbol, status, and expiration indexes

Still not implemented in `8D2` alone:

- repositories or services
- API routes
- open/close lifecycle behavior
- staged options orders
- options positions/trades runtime behavior
- `commission_per_contract` application
- frontend UI

## 8D3 repository/service contracts implemented now

The dedicated options persistence branch now has internal repository/service
contracts without any route or UI wiring.

Implemented now:

- `OptionPaperStructureInput` and typed option paper record contracts in
  `src/macmarket_trader/domain/schemas.py`
- `prepare_option_paper_structure(...)` in
  `src/macmarket_trader/options/paper_contracts.py`
- `OptionPaperRepository` in `src/macmarket_trader/storage/repositories.py`

Current repository/service contract coverage:

- create option paper order header plus legs
- create option paper position header plus legs
- create option paper trade header plus legs
- fetch option paper orders with legs
- fetch option paper positions with legs
- list open option paper positions for one user
- list option paper trades for one user
- structure validation through existing payoff helpers before persistence

Current validation boundaries:

- `market_mode=options` required
- supported structure types limited to:
  - `long_call`
  - `long_put`
  - `vertical_debit_spread`
  - `iron_condor`
- naked short single-leg structures blocked
- multi-expiration structures blocked
- invalid quantity / multiplier / strike / premium blocked through existing
  payoff validation

Still not implemented in `8D3` alone:

- API routes
- open paper option structure behavior
- close paper option structure behavior
- `commission_per_contract` application
- assignment/exercise handling
- frontend UI

## 8D4 open paper option structure implemented now

The first runtime lifecycle step now exists without adding any frontend UI.

Implemented now:

- `open_paper_option_structure(...)` in
  `src/macmarket_trader/options/paper_open.py`
- `OptionPaperRepository.open_structure(...)` in
  `src/macmarket_trader/storage/repositories.py`
- protected route at `POST /user/options/paper-structures/open`
- typed open-response contract in
  `src/macmarket_trader/domain/schemas.py`

Current runtime behavior:

- validates and normalizes the requested structure through
  `prepare_option_paper_structure(...)`
- accepts supported defined-risk structures only
- creates one options-specific paper order header plus legs
- creates one options-specific paper position header plus legs
- preserves `execution_enabled=false`
- returns an operator-facing paper-only summary with:
  - order id
  - position id
  - structure type
  - net debit / credit
  - max profit / loss
  - breakevens
  - normalized legs

Current guardrails:

- no equity orders, positions, or trades are created
- no replay runs are created
- no recommendation rows are created
- no staged options orders are created
- naked short single-leg structures remain blocked
- multi-expiration structures remain blocked
- no commissions are applied yet
- no expiration settlement exists yet
- no frontend operator UI exists yet

## 8D5 manual close paper option structure implemented now

The second runtime lifecycle step now exists without adding any frontend UI.

Implemented now:

- `close_paper_option_structure(...)` in
  `src/macmarket_trader/options/paper_close.py`
- `OptionPaperRepository.close_structure_manual(...)` in
  `src/macmarket_trader/storage/repositories.py`
- protected route at
  `POST /user/options/paper-structures/{position_id}/close`
- typed close-request and close-response contracts in
  `src/macmarket_trader/domain/schemas.py`

Current runtime behavior:

- validates user-scoped open positions only
- requires all open position legs to be closed together
- accepts `manual_close` only in the current slice
- requires non-negative exit premiums per leg
- blocks cross-user close attempts, duplicate close attempts, unknown legs,
  and partial-leg close attempts
- updates option position and leg rows to closed state
- creates one options-specific trade header plus trade legs
- stores gross P&L only; `total_commissions` and `net_pnl` remain null until
  `8D6`

Current guardrails:

- no equity orders, positions, or trades are created
- no replay runs are created
- no recommendation rows are created
- no staged options orders are created
- no expiration settlement exists yet
- no `commission_per_contract` application exists yet
- no frontend operator UI exists yet

## Draft contract and payload direction

These are future payload sketches only. They are not approved for runtime yet.

### Paper option structure open request

```json
{
  "market_mode": "options",
  "lifecycle_mode": "paper_open",
  "structure_type": "vertical_debit_spread",
  "underlying_symbol": "AAPL",
  "expiration": "2026-05-15",
  "workflow_source": "polygon",
  "source": "analysis_setup",
  "recommendation_id": null,
  "options_replay_preview_id": null,
  "contracts": 1,
  "legs": [
    {
      "leg_index": 0,
      "action": "buy",
      "right": "call",
      "strike": 205.0,
      "quantity": 1,
      "multiplier": 100,
      "premium": 4.2,
      "label": "long call"
    },
    {
      "leg_index": 1,
      "action": "sell",
      "right": "call",
      "strike": 215.0,
      "quantity": 1,
      "multiplier": 100,
      "premium": 1.6,
      "label": "short call"
    }
  ],
  "net_debit": 2.6,
  "net_credit": null,
  "max_profit": 740.0,
  "max_loss": 260.0,
  "breakevens": [207.6],
  "operator_note": "Paper-only open from approved options lifecycle path."
}
```

### Paper option structure close request

```json
{
  "market_mode": "options",
  "lifecycle_mode": "paper_close",
  "position_id": 41,
  "close_mode": "manual",
  "closed_at": "2026-05-08T14:45:00Z",
  "underlying_symbol": "AAPL",
  "underlying_settlement_price": null,
  "legs": [
    {
      "leg_index": 0,
      "close_premium": 5.8
    },
    {
      "leg_index": 1,
      "close_premium": 0.5
    }
  ],
  "close_reason": "target_window_hit",
  "operator_note": "Paper close only. No broker routing."
}
```

### Option leg fill snapshot

```json
{
  "leg_index": 0,
  "action": "buy",
  "right": "call",
  "strike": 205.0,
  "quantity": 1,
  "multiplier": 100,
  "premium": 4.2,
  "provider_symbol": "AAPL250515C00205000",
  "fill_mode": "paper_assumed"
}
```

### Option paper position summary

```json
{
  "position_id": 41,
  "market_mode": "options",
  "status": "open",
  "structure_type": "vertical_debit_spread",
  "underlying_symbol": "AAPL",
  "expiration": "2026-05-15",
  "days_to_expiration": 16,
  "contracts": 1,
  "net_debit": 2.6,
  "net_credit": null,
  "max_profit": 740.0,
  "max_loss": 260.0,
  "breakevens": [207.6],
  "commission_per_contract": 0.95,
  "estimated_open_commission": 1.9,
  "estimated_close_commission": 1.9,
  "workflow_source": "polygon",
  "source": "analysis_setup",
  "legs": [
    {
      "leg_index": 0,
      "action": "buy",
      "right": "call",
      "strike": 205.0,
      "quantity": 1,
      "multiplier": 100,
      "open_premium": 4.2
    }
  ]
}
```

### Option close result

```json
{
  "trade_id": 55,
  "position_id": 41,
  "market_mode": "options",
  "status": "closed_manual",
  "structure_type": "vertical_debit_spread",
  "underlying_symbol": "AAPL",
  "expiration": "2026-05-15",
  "gross_realized_pnl": 310.0,
  "net_realized_pnl": 306.2,
  "open_commission": 1.9,
  "close_commission": 1.9,
  "total_commission": 3.8,
  "commission_per_contract": 0.95,
  "net_debit": 2.6,
  "net_credit": null,
  "max_profit": 740.0,
  "max_loss": 260.0,
  "breakevens": [207.6],
  "legs": [
    {
      "leg_index": 0,
      "gross_pnl": 160.0,
      "net_pnl": 159.05
    },
    {
      "leg_index": 1,
      "gross_pnl": 150.0,
      "net_pnl": 149.05
    }
  ]
}
```

## Fee model design

Future `8D` should use `commission_per_contract` only for options.

Planned rules:

- per contract
- per leg
- on both open and close
- separate from `commission_per_trade`, which remains the equity fee model

Planned math:

- opening leg commission:
  `contracts * commission_per_contract`
- closing leg commission:
  `contracts * commission_per_contract`
- total structure commission:
  sum across all open and close legs

Leg-level gross P&L:

- long leg:
  `(close_premium - open_premium) * contracts * multiplier`
- short leg:
  `(open_premium - close_premium) * contracts * multiplier`

Structure-level P&L:

- `gross_realized_pnl = sum(leg gross pnl)`
- `net_realized_pnl = gross_realized_pnl - total_commission`

Backward compatibility:

- keep `commission_per_trade` untouched for equities
- reuse the existing per-user settings source of truth:
  `AppUserModel.commission_per_contract`
- do not overload Phase 7 equity fee helpers with options semantics

## Relationship to 8C replay preview

`8D` should reuse:

- `src/macmarket_trader/options/payoff.py`
- `src/macmarket_trader/options/replay_preview.py`
- the same defined-risk validation rules and blocked reasons where possible

`8D` should not depend on:

- equity replay DB rows
- `RecommendationService.generate()`
- equity `OrderIntent` / `OrderRecord` / `FillRecord`
- equity `ReplayEngine`

Recommended reuse pattern:

- reuse payoff helpers for validation and terminal payoff calculations
- reuse replay-preview-style structure normalization at the options boundary
- keep lifecycle persistence separate from preview contracts

## Supported first structures

Safest first lifecycle support:

1. vertical debit spreads
2. iron condor
3. optional long call / long put only after the structure-aware open/close
   contract is proven stable

Blocked or deferred:

- naked short options
- covered calls until inventory and assignment modeling exists
- calendars, diagonals, and ratio spreads until dedicated valuation rules
  exist

Why vertical debit spread first:

- two legs
- one net debit
- straightforward max loss and close semantics
- easiest bridge from existing 8C payoff math into real paper lifecycle

Why iron condor second:

- already supported in 8C payoff math
- still defined-risk
- exercises four-leg debit/credit and wing-risk bookkeeping without requiring
  naked-short support

## Future UI implications

This section is planning only. It does not authorize UI work now.

Future operator surfaces should separate:

- read-only research preview
- read-only replay preview
- actual paper options lifecycle

Recommended placement:

- open paper option structures should later appear in Orders as a distinct
  options section, not mixed into the current equity open-position list
- close action should later live on the structure row, with leg summaries
  visible before confirmation
- closed options structures should later appear in a dedicated closed-trades
  section with gross/net commission detail

Important UX distinction:

- replay preview must remain visibly non-persisted
- paper lifecycle must remain visibly paper-only
- neither surface may imply live routing

## Test plan for implementation

Before any `8D` implementation begins, later slices should add:

- schema and migration tests
- open structure lifecycle tests
- close structure lifecycle tests
- commission-per-contract tests
- gross vs net realized P&L tests
- explicit defined-risk validation tests
- blocked naked-short tests
- blocked assignment/exercise automation tests
- no live-routing tests

Equity regression gates required alongside `8D`:

- current paper order lifecycle tests
- current close/reopen tests
- current Phase 7 fee-preview tests
- current replay and recommendations regression anchors

## Future implementation slices

### 8D1 - Design checkpoint

Complete when:

- schema approach is chosen
- lifecycle boundaries are documented
- payload direction is documented
- fee-model direction is documented

Must not change:

- any runtime behavior

### 8D2 - Schema and migration only

Complete when:

- approved options persistence tables exist
- focused schema and migration tests pass
- no routes or UI depend on them yet

Must not change:

- current equity tables or lifecycle semantics beyond necessary coexistence

### 8D3 - Repository and service contracts

Complete when:

- options-specific repositories or service helpers exist
- structure and leg persistence is auditable
- focused repository/service contract tests pass
- no operator UI is enabled yet

Must not change:

- current equity repositories or replay behavior

### 8D4 - Open paper option structure

Complete when:

- supported structures can open in paper mode
- lineage and paper-only caveats persist correctly

Must not change:

- equity order staging behavior

### 8D5 - Close paper option structure

Complete when:

- supported structures can close manually in paper mode
- gross realized P&L is deterministic
- blocked wrong-user, double-close, and invalid-leg paths are tested

Must not change:

- equity close lifecycle

### 8D6 - `commission_per_contract` net P&L

Complete when:

- contract-level commission is applied deterministically
- gross and net P&L stay explicit and operator-readable

Must not change:

- Phase 7 equity fee math

### 8D7 - Frontend operator UI

Complete when:

- Orders exposes the options paper lifecycle clearly
- read-only replay preview remains distinct from persisted paper lifecycle

Must not change:

- current equity Orders behavior beyond mode-aware coexistence

### 8D8 - Tests and docs closure

Complete when:

- lifecycle tests pass
- equity regressions pass
- supported structures and deferred items are documented accurately

## Guardrails

- no equity lifecycle breakage
- no live trading
- no brokerage routing
- the currently approved runtime lifecycle behavior in the current branch is:
  - `8D4` open-only paper structure
  - `8D5` manual close paper structure
- no expiration settlement until a later approved slice
- no automatic assignment or exercise in the early lifecycle pass
- no naked shorts early
- no margin assumptions unless explicitly modeled
- no hidden reuse of equity `OrderIntent` / fill semantics for options

## Recommended implementation prompt after this checkpoint

After the completed `8D5` manual-close paper lifecycle slice, the safest next
implementation prompt is:

- `Implement 8D6 only: apply commission_per_contract to the dedicated options
  paper lifecycle branch, keeping gross versus net P&L explicit, with no
  frontend UI yet, no live routing, and no changes to the existing equity fee
  math.`
