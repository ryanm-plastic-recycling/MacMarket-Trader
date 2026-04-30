# Phase 8 Options Architecture Plan

Last updated: 2026-04-30

## Planning posture

This document is the Phase 8 master plan for options support in
MacMarket-Trader. It tracks completed checkpoints plus the remaining
implementation plan.

It still does not authorize:

- live trading
- brokerage routing
- staged options orders
- secrets or provider credential work

Current planning state:

- `8A` complete: architecture and contract planning foundations
- `8B` complete: read-only, non-persisted options research visibility in
  Analysis / Recommendations
- `8C` complete for the current read-only, non-persisted replay-preview
  scope: `8C2` pure payoff math, `8C3` read-only replay preview contract,
  `8C4` operator UI preview, and `8C5` closure review/tests/docs alignment
  are complete
- `8D` complete for the current paper-only manual-close lifecycle scope:
  `8D1` design checkpoint, `8D2` dedicated schema foundation, `8D3`
  repository/service contracts, `8D4` open paper option structure behavior,
  `8D5` manual close behavior, `8D6` `commission_per_contract` net-P&L
  modeling, `8D7` frontend operator UI, and `8D8` closure review/tests/docs
  alignment are complete
- `8E` complete for the current Recommendations options risk/operator UX
  surface
- `8F` complete: Phase 8 is closed for the current scoped paper-first options
  capability
- Phase 9 is also closed for the current options operator parity,
  provider/source/as-of, and Recommendations Expected Range visualization
  scope; remaining provider-depth, Analysis visualization, replay placement,
  settlement, assignment/exercise, and live routing work stays deferred

## Current repo anchors

Phase 8 should extend existing repo anchors rather than replace them:

- `README.md` defines the product center and paper-only posture
- `TradeRecommendation.market_mode` already exists and defaults to `equities`
- `domain/schemas.py` already contains:
  - `InstrumentIdentity`
  - `OptionContractContext`
  - `OptionStructureLeg`
  - `OptionStructureContext`
  - `ExpectedRange`
- `admin.py` already builds options research setup payloads
- `market_data.py` already exposes Polygon `options_chain_preview(...)`
- Analysis / Recommendations already expose read-only options research preview
- `app_users.commission_per_contract` already exists and is now applied to the
  dedicated options paper lifecycle branch only
- current replay, orders, fills, positions, and trades remain equity-centric

## Phase 8 guardrails

- Keep options mode explicitly separate from equity execution-prep logic
- Keep the platform paper-only
- Do not route options through equity `RecommendationService.generate()`
- Do not stretch current equity replay persistence into pseudo-options support
- Do not stage options orders before the correct lifecycle phase
- Do not imply live provider readiness equals execution enablement
- Do not support naked short options in early phases
- Do not automate assignment or exercise in early phases
- Do not introduce margin assumptions unless they are explicitly modeled later

## Phase 8 execution map

### 8A - Architecture and contract planning

Status:

- complete

Complete means:

- Phase 8 boundaries and guardrails are documented
- repo anchors and likely implementation touchpoints are identified
- research-only versus replay versus paper-lifecycle scopes are separated

Not complete:

- any runtime behavior

### 8B - Read-only options research visibility

Status:

- complete for the current non-persisted research-only scope

Complete means:

- Analysis / Recommendations can show options research safely
- options mode stays read-only and paper-only
- queue/promote/replay/order/staging CTAs stay suppressed
- missing values and blocked states render safely

Not complete:

- persisted options recommendations
- options replay
- options orders, fills, positions, or trades

### 8C - Read-only options replay preview

Status:

- complete for the current read-only, non-persisted replay-preview scope:
  `8C2`, `8C3`, `8C4`, and `8C5`

Detailed design:

- [options-replay-design.md](options-replay-design.md)

Scope:

- read-only, non-persisted replay preview for defined-risk structures
- separate request/response branch from current equity replay
- no schema changes in the safest first slice
- no staged orders, fills, positions, or trades

Complete means:

- an operator can review a deterministic replay preview for supported
  structures without changing equity replay behavior
- vertical debit spreads work first
- iron condor is supported shortly after on the same payoff helper foundation
- blocked reasons and missing-data states are explicit
- Expected Move / Expected Range remains visible as contextual research input
  and does not modify expiration payoff math or imply execution approval

Not complete:

- options replay persistence
- options order enablement
- mark-to-market parity
- advanced Expected Move / Expected Range visualization beyond the current
  contextual summary
- assignment / exercise automation

### 8D - Options paper lifecycle

Status:

- `8D1` design checkpoint complete
- `8D2` dedicated schema/migration foundation complete
- `8D3` repository/service contracts complete
- `8D4` open paper option structure complete
- `8D5` manual close paper option structure complete
- `8D6` options contract-commission net-P&L modeling complete
- `8D7` frontend operator UI complete
- `8D8` closure review/tests/docs alignment complete

Detailed design:

- [options-paper-lifecycle-design.md](options-paper-lifecycle-design.md)

Scope:

- option contract identity
- leg-aware paper order contract
- structure open / close lifecycle
- realized gross / net P&L
- `commission_per_contract` application

Complete means:

- supported defined-risk structures can be opened and closed in paper mode
- structure-level and leg-level summaries remain auditable
- current equity paper lifecycle remains intact

Planned now:

- dedicated options persistence is recommended over extending the current
  equity write tables
- dedicated `paper_option_*` tables now exist as the approved schema
  foundation
- dedicated repository/service contracts now exist for typed create/fetch
  access to the options persistence branch
- dedicated paper-only open and manual-close lifecycle paths now exist
- `commission_per_contract` now applies to the dedicated options paper
  lifecycle branch without changing the equity fee model
- Recommendations now exposes a separate paper-only operator panel for
  open/manual-close lifecycle actions with explicit commission guardrails
- the closure pass now includes a manual smoke checklist and explicit audit
  coverage for user scoping, gross/net commission math, proxy boundaries, and
  paper-only UX wording

Not complete:

- expiration settlement mode
- broader Orders dashboard parity for durable option positions/trades
- naked short options
- assignment / exercise automation
- partial fills in the earliest lifecycle slice
- live brokerage execution

### 8E - Operator risk UX

Status:

- complete for the current Recommendations options risk/operator UX surface

Detailed design:

- [options-risk-ux-design.md](options-risk-ux-design.md)

Scope:

- strategy summary
- legs table
- debit / credit
- max profit / max loss
- breakevens
- DTE / expiration context
- payoff preview surfaces
- warning and caveat system

Complete means:

- operators can understand structure risk and data quality before using later
  paper-lifecycle features
- paper-only and non-execution caveats are visible everywhere they matter

Not complete:

- full chart-heavy payoff tooling in the first UX slice
- live-liquidity or routing realism
- broader provider/source/as-of parity later landed in Phase 9C
- the first reusable Expected Range visualization later landed in Phase 9D

### 8F - Closure criteria

Status:

- complete for the current scoped paper-first options capability

Complete means:

- supported options flows are coherent from research to replay to paper
- tests cover supported defined-risk options flows and equity regression gates
- provider/source labeling remains truthful across the workflow
- deferred items are explicitly documented instead of implied complete

Detailed test and closure matrix:

- [options-test-plan.md](options-test-plan.md)

## Provider and data assumptions

- Provider readiness remains separate from execution enablement
- Polygon chain preview is suitable for early read-only research anchors, not
  for full execution parity
- underlying bars remain the primary replay path anchor
- expected range remains contextual, not a substitute for payoff math
- premium assumptions must be explicit before replay or lifecycle math is
  trusted
- Alpaca paper readiness remains a provider-readiness concept until a later,
  explicit execution phase
- FRED and news remain supporting workflow context, not options execution
  dependencies

## Conservative implementation sequence

The safest future implementation order is:

1. `8C2.1` pure option payoff math module and tests
2. `8C2.2` vertical debit spread payoff tests and helpers
3. `8C2.3` iron condor payoff tests and helpers
4. `8C3.1` read-only replay preview contract
5. `8C4.1` replay preview UI
6. `8C5` replay tests and docs closure
7. `8D1` schema/lifecycle design checkpoint before any migration work
8. `8D2` dedicated schema/migration foundation
9. `8D3` repository and service contracts
10. `8D4` open paper option structure
11. `8D5` close paper option structure
12. `8D6` `commission_per_contract` application
13. `8D7` operator UI
14. `8D8` lifecycle tests/docs closure
15. `8E1` operator risk UX improvements
16. `8F` full closure review

Why this order:

- it proves deterministic payoff math before route/UI complexity
- it keeps equity replay and paper-order logic isolated
- it delays schema pressure until there is a validated replay contract
- it keeps options execution semantics out of the product until the right phase

Current implementation note:

- `src/macmarket_trader/options/payoff.py` provides the isolated 8C2 payoff
  foundation for long-option primitives, vertical debit spreads, and iron
  condor math
- `POST /user/options/replay-preview` plus the Recommendations-side replay
  preview UI now define the current 8C boundary without adding schema,
  persistence, staged orders, or execution enablement
- `POST /user/options/paper-structures/open` and
  `POST /user/options/paper-structures/{position_id}/close` now define the
  current 8D4/8D5 boundary for open/manual-close paper options lifecycle
  persistence, using dedicated options tables and repository contracts without
  adding staged options orders, expiration settlement, commissions, or live
  routing
- Recommendations now carries the current 8E/8F risk/operator UX closure, and
  Phase 9 adds durable Orders visibility, source/as-of parity, and a compact
  Recommendations Expected Range visualization without changing backend,
  provider, lifecycle, commission, equity, payoff, or recommendation math
- Phase 10 now organizes the remaining deferred work into safe near-term
  polish, medium-risk design checkpoints, and explicitly later implementation
  tracks before any settlement, assignment/exercise, routing, probability,
  margin, persisted recommendation, replay-persistence, or crypto runtime work

## Deferred items that do not block current options closure

- persisted options recommendations
- options replay persistence in existing replay tables
- staged options orders
- options fills, positions, and trades
- assignment / exercise automation
- naked short support
- covered calls that require inventory/assignment modeling
- mark-to-market parity and Greek-driven valuation
- live routing or brokerage execution
- optional Analysis Expected Range visualization and richer replay placement
- future provider-depth or live-probe work

## Companion documents

- [options-replay-design.md](options-replay-design.md)
- [options-paper-lifecycle-design.md](options-paper-lifecycle-design.md)
- [options-risk-ux-design.md](options-risk-ux-design.md)
- [options-test-plan.md](options-test-plan.md)
