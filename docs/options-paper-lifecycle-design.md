# Phase 8D Options Paper Lifecycle Design

Last updated: 2026-05-03

## Purpose

This document defines the `8D` design checkpoint, schema foundation,
repository/service contracts, and current runtime boundary for options paper
lifecycle support.

`8D1` design, `8D2` schema foundation, `8D3` repository/service contracts,
`8D4` open paper option structure behavior, `8D5` manual close paper
option structure behavior, `8D6` `commission_per_contract` net-P&L
modeling, `8D7` frontend operator UI, `8D8` closure review/tests/docs
alignment, and the follow-on options position review/lifecycle integrity
evidence pass are now implemented. The dedicated options persistence branch
exists and now authorizes supported defined-risk structures to open and
close manually through options-specific paper-only backend paths, with
Recommendations hosting the first operator UI for the persisted paper
lifecycle and Orders showing a review-only active options position review
section. It still does not authorize:

- options order staging
- expiration settlement behavior
- live routing
- brokerage execution
- automatic exits, rolling, or adjustments
- automatic assignment or exercise handling

## Options Position Review Implemented

Backend:

```http
GET /user/options/paper-structures/review
```

Frontend proxy:

```http
GET /api/user/options/paper-structures/review
```

The endpoint returns one current-user open options paper structure review per
persisted open structure. Closed structures, equity paper positions, and other
users' structures are excluded by default. The response is intentionally
structure/leg shaped instead of reusing the equity
`/user/paper-positions/review` shape.

Each structure review includes:

- structure id, underlying, strategy type, side/direction, open time,
  expiration, DTE, contracts, and multiplier assumption
- opening debit/credit and opening commissions using the current user
  `commission_per_contract`
- persisted max profit, max loss, breakevens, and payoff summary
- current mark and unrealized P&L fields when safe data exists
- risk-calendar assessment for the underlying
- expiration status
- deterministic action classification and action summary
- warnings, missing-data entries, provenance, and leg reviews

Each leg review includes:

- stable persisted leg id
- underlying, expiration, right, strike, long/short side, contracts, and
  opening premium
- current mark premium and estimated leg P&L when safe data exists
- mark method, IV, open interest, Greeks, stale flag, and provider as-of
  metadata when supplied by the provider snapshot
- market-data source/fallback/as-of fields and missing-data entries

Provider-backed option mark support:

- options review now queries Polygon/Massive contract snapshots through
  `/v3/snapshot/options/{underlying}/{option}` when Polygon/Massive is the
  configured market data provider and the account plan permits options
  snapshots
- option symbols are generated in Polygon OCC-style form, for example
  `O:AAPL260515C00205000`
- leg mark precedence is deterministic:
  1. valid bid/ask midpoint (`quote_mid`)
  2. valid latest trade (`last_trade`)
  3. previous/day close only as an explicitly stale
     `prior_close_fallback`
  4. `unavailable`
- stale, zero, null, or missing values are not used as fresh marks
- if any required leg mark is missing or stale, structure-level current mark
  and unrealized P&L remain unavailable and the review stays
  `mark_unavailable`
- IV, open interest, Greeks, and underlying price are displayed only when the
  provider supplies them; MacMarket does not calculate Greeks in this pass
- no Black-Scholes model, synthetic mark, demo price, or stale close is used
  as a real current option mark
- provider permission/plan errors are sanitized and surfaced as missing-data
  context instead of exposing secrets

Supported structures in this pass:

- `long_call`
- `long_put`
- `vertical_debit_spread`
- `iron_condor`

Unsupported or malformed persisted structures return `review_unavailable` with
missing-data entries such as `unsupported_strategy_type` or `option_legs`.

Action classification precedence:

1. `review_unavailable`
2. `mark_unavailable`
3. `expiration_due`
4. `max_loss_near`
5. `max_profit_near`
6. `close_candidate`
7. `adjustment_review`
8. `expiration_warning`
9. `profitable_hold`
10. `losing_hold`
11. `hold_valid`

These are human review classifications only. They do not create close orders,
rolls, adjustments, scale-ins, broker orders, or live trades.

When all required leg marks are fresh, the review can now classify
`max_profit_near`, `max_loss_near`, `profitable_hold`, `losing_hold`,
`close_candidate`, or `adjustment_review` from the deterministic mark-to-open
P&L context. These classifications remain review-only and never stage or
submit an options action.

Risk-calendar behavior:

- risk-calendar `restricted` or `no_trade` state warns against adding or
  adjusting exposure
- it does not recommend closing solely because new entries are blocked
- missing event evidence is surfaced as warnings/missing data

Options sandbox reset behavior:

- the current equity paper sandbox reset remains equity scoped
- persisted options paper orders, structures, legs, and trades are not reset
  by `POST /user/paper/reset`
- a future options reset path should be explicit, current-user scoped, and
  separately tested before release

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
- `opening_commissions` and `closing_commissions`
- `total_commissions`
- `net_pnl`
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
  - `commission_per_contract`
  - opening commissions
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
- no expiration settlement exists yet
- the `8D4` slice itself does not require frontend UI; operator UI is added
  later in `8D7`

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
- stores gross P&L plus explicit paper commission totals and net P&L
- persists leg-level paper commission and net P&L values on trade legs

Current guardrails:

- no equity orders, positions, or trades are created
- no replay runs are created
- no recommendation rows are created
- no staged options orders are created
- no expiration settlement exists yet
- the `8D5` slice itself does not require frontend UI; operator UI is added
  later in `8D7`

## 8D6 `commission_per_contract` net P&L implemented now

The dedicated options paper lifecycle branch now applies
`commission_per_contract` deterministically without changing the existing
equity fee model.

Implemented now:

- user-scoped `commission_per_contract` sourcing through the existing Phase 7
  settings/default path
- open-response exposure of:
  - `commission_per_contract`
  - `opening_commissions`
- manual-close computation of:
  - `gross_pnl`
  - `opening_commissions`
  - `closing_commissions`
  - `total_commissions`
  - `net_pnl`
- trade persistence of:
  - `total_commissions`
  - `net_pnl`
- trade-leg persistence of:
  - `leg_commission`
  - `leg_net_pnl`

Current fee rules:

- commission is per contract, per leg
- commission applies on both open and close
- contract multiplier affects P&L math but does not multiply commissions
- zero commission keeps `net_pnl == gross_pnl`
- Phase 7 `commission_per_trade` equity behavior remains unchanged

Current audit limitation:

- `opening_commissions` is currently derived/reconstructed from position legs
  and the current `commission_per_contract` when closing and listing paper
  option summaries. If `commission_per_contract` changes between open and
  close, the displayed opening commission split can differ from the original
  open-time estimate. This is acceptable for the current paper-only scope; a
  future auditability pass should persist open-time commission snapshots if
  stronger fee reconstruction is needed.

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

The current `8D6` implementation uses `commission_per_contract` only for the
dedicated options paper lifecycle branch.

## 8D7 frontend operator UI implemented now

Recommendations now hosts the first operator-facing UI for the dedicated
options paper lifecycle branch.

Implemented now:

- same-origin frontend proxies for:
  - `POST /user/options/paper-structures/open`
  - `POST /user/options/paper-structures/{position_id}/close`
- Recommendations-side paper option lifecycle panel inside the options
  research preview
- explicit separation between:
  - read-only replay payoff preview
  - persisted paper option lifecycle actions
- settings-page commission guardrails for `commission_per_contract`
- in-memory manual close inputs/results for the newly opened paper option
  position only

Current operator behavior:

- operators can open a supported paper option structure from the existing
  options research preview
- operators see:
  - structure summary
  - normalized legs
  - net debit/credit
  - max profit/loss
  - breakevens
  - estimated opening commissions
  - estimated open + close commissions
- operators can manually close the newly opened paper option position by
  entering one exit premium per leg
- close results render:
  - gross P&L
  - opening commissions
  - closing commissions
  - total commissions
  - net P&L
  - leg-level gross/commission/net detail

Current commission guardrails:

- settings explicitly label commission as "per contract"
- settings and Recommendations both say:
  - not per share
  - do not multiply by 100
- settings and Recommendations both show:
  - commission formula:
    `commission per contract x contracts x legs x open/close events`
  - a compact iron-condor example
- current structure estimates stay paper-only and do not imply broker routing

Current guardrails:

- replay payoff preview remains read-only and non-persisted
- paper open/close UI remains paper-only and broker-order-free
- no expiration-settlement UI exists yet
- no assignment/exercise UI exists yet
- broader Orders dashboard parity for durable option positions/trades is now
  partially addressed by `10B1` display/readability polish; lifecycle actions
  from Orders remain deferred

Current rules:

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

Current `10B1` Orders display/readability polish:

- Orders now treats durable paper-options rows as display-only paper lifecycle
  records sourced from structures saved in Recommendations
- open paper positions and manually closed paper positions are visually
  separated with compact status labels
- rows show existing persisted fields only: underlying, structure type,
  opened/closed timestamps, expiration, leg count, opening debit/credit,
  max profit/loss, breakevens, opening/closing/total commissions, gross P&L,
  and net P&L where available
- leg details are expandable and show action, right, strike, expiration,
  contracts, multiplier, entry premium, exit premium, leg gross P&L, leg
  commission, and leg net P&L when those fields exist
- the section repeats that no broker orders were sent, manual close remains in
  the Recommendations workflow, and provider/source/as-of metadata may be
  limited on durable lifecycle rows
- no open, close, settlement, assignment/exercise, replay, routing, or
  brokerage action was added to Orders

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
- trade rows and trade-leg rows persist fee-aware values for the supported
  manual-close path

Must not change:

- Phase 7 equity fee math

### 8D7 - Frontend operator UI

Complete when:

- Recommendations exposes the options paper lifecycle clearly for the current
  paper-only scope
- settings make `commission_per_contract` unmistakable as per contract, not
  per share or contract multiplier
- read-only replay preview remains distinct from persisted paper lifecycle
- paper open/manual-close actions stay visibly paper-only

Must not change:

- current equity Orders behavior beyond mode-aware coexistence

### 8D8 - Tests and docs closure

Complete when:

- lifecycle tests pass
- equity regressions pass
- supported structures and deferred items are documented accurately

Implemented now:

- backend lifecycle tests pass for schema, repository contracts, open path,
  manual close path, commission modeling, payoff math, replay preview
  contract, and equity regression anchors
- frontend tests pass for settings commission copy, replay-preview
  separation, paper open/manual-close surfaces, proxy routes, and safe
  missing-value rendering
- roadmap/design docs now reflect `8D1` through `8D8` accurately for the
  current paper-only manual-close scope
- a short manual smoke checklist now exists for operator verification

Manual smoke checklist:

1. Set `commission_per_contract` in Settings and confirm the guardrail copy
   says "Not per share. Do not multiply by 100."
2. Open Recommendations in options mode and confirm the research preview
   loads with expected range context and no equity queue/promote actions.
3. Run Replay payoff preview and confirm it remains read-only and
   non-persisted.
4. Open paper option structure and confirm the page shows estimated opening
   and open + close commissions.
5. Enter exit premium per leg and manually close the paper structure.
6. Verify gross P&L, opening commissions, closing commissions, total
   commissions, and net P&L.
7. Verify the page stays paper-only and does not present live-trading or
   brokerage-routing language.

## Guardrails

- no equity lifecycle breakage
- no live trading
- no brokerage routing
- the currently approved runtime lifecycle behavior in the current branch is:
  - `8D4` open-only paper structure
  - `8D5` manual close paper structure
  - `8D6` contract-commission net-P&L modeling
  - `8D7` compact Recommendations-side operator UI
  - `8D8` closure/docs/test alignment
- no expiration settlement until a later approved slice
- no automatic assignment or exercise in the early lifecycle pass
- no naked shorts early
- no margin assumptions unless explicitly modeled
- no hidden reuse of equity `OrderIntent` / fill semantics for options

## Recommended implementation prompt after this checkpoint

After the completed `8D8` closure pass, the safest next implementation prompt
is:

- `Implement 8E1 only: add compact options risk-summary UX for supported
  paper-only structures, covering legs, debit/credit, max profit/loss,
  breakevens, DTE, and paper-only caveats, with no expiration settlement,
  no assignment/exercise automation, and no live-routing changes.`
