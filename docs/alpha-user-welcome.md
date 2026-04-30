# MacMarket-Trader Operator Welcome Guide

Last updated: 2026-04-30

This is the practical welcome/training guide for MacMarket-Trader operators.
It is written for:

- the operator using the console day to day
- the project owner learning or demoing the system
- future AI/Codex agents that need accurate high-level usage context

MacMarket-Trader is still paper-only. Nothing in this guide authorizes live
trading, brokerage routing, or real-money execution.

## 1. What MacMarket-Trader is

MacMarket-Trader is a private operator console for research, deterministic
trade review, replay validation, and paper-only lifecycle tracking.

Current reality:

- it is a paper-first trading intelligence system
- equities are the current guided paper workflow center
- options now have:
  - research preview
  - replay payoff preview
  - a separate paper-only open/manual-close lifecycle
- it is not live trading
- it is not brokerage execution
- it does not route real-money orders

The product center is:

1. Analysis / Strategy Workbench
2. Recommendations
3. Replay
4. Orders

For options, the current operator center is Analysis plus Recommendations for
setup, payoff preview, and open/manual-close actions, with Orders now
providing durable paper-options position/trade visibility outside the
Recommendations page.

## 2. Current operating modes

| Mode | What it does now | What it does not do |
| --- | --- | --- |
| Equities mode | Full operator flow: Analysis -> Recommendations -> Replay -> Orders -> close paper trade | No live routing |
| Options research preview | Shows structure, legs, expected range status, chain preview when available, and chart/research context | Not execution support |
| Options replay payoff preview | Read-only, non-persisted expiration payoff preview for supported defined-risk structures | Does not create replay runs, orders, positions, or trades |
| Paper options lifecycle | Persists a paper-only options position and supports manual close for supported structures | No expiration settlement, no assignment/exercise automation, no live routing |
| Provider health / operator readiness | Shows provider configuration, fallback/blocking truth, and operator trust state | Does not enable live trading |

Two workflow styles also matter:

- Guided mode: the main equities workflow with context continuity across
  Analysis -> Recommendations -> Replay -> Orders
- Explorer mode: browse and review existing workflow records without the
  guided auto-advance behavior

## 3. Basic user flow

### Core workflow

1. Open **Analysis**.
2. Pick a symbol.
3. Choose the correct market mode.
4. Review chart context, workflow source, strategy rationale, and levels.
5. Continue based on mode.

### Equities flow

1. In Analysis, review the setup and chart.
2. Create the recommendation.
3. Open **Recommendations** and review the persisted lineage.
4. Run **Replay** to validate the path.
5. If the replay is stageable, continue into **Orders**.
6. Stage the paper order, monitor the paper position, and close it when ready.
7. Review realized paper results.

### Options flow

1. In Analysis, switch to **options** market mode.
2. Review the options research preview:
   - structure type
   - legs
   - expiration / DTE
   - expected range status
   - chain preview when available
3. In **Recommendations**, use:
   - **Guided options workflow** to stay oriented through structure review,
     payoff preview, paper save, manual close, and result review
   - **Structure risk** for a compact view of max profit/loss, breakevens,
     Expected Range status, replay-preview status, and current paper
     lifecycle state
   - **Replay payoff preview** for read-only expiration payoff inspection
   - **Paper option lifecycle** for paper-only open/manual-close actions
4. Open the paper option structure only if the structure is complete and
   supported.
5. Close manually by entering one exit premium per leg.
6. Review gross P&L, commissions, and net P&L.
7. Open **Orders** later to review the durable saved paper option position or
   closed paper trade result outside Recommendations.

## 4. Options training

Keep these distinctions clear:

- **Options research preview** is not execution support.
- **Replay payoff preview** is read-only and non-persisted.
- **Paper option lifecycle** creates persisted paper-only option positions and
  trades for the currently supported lifecycle scope.
- **Save as paper option position** means a paper-only record is created.
  No broker order is sent.
- **Manual close** requires one exit premium per leg.
- **Expiration settlement** is deferred.
- **Assignment/exercise automation** is deferred.
- **Naked shorts** are blocked.
- **Live routing** is not available.

Current supported operator expectation:

- use research preview to inspect the setup
- use replay payoff preview to inspect expiration payoff math
- use the paper lifecycle panel only when you intentionally want persisted
  paper-state behavior

Do not confuse replay payoff preview with paper lifecycle:

- replay preview stays read-only and non-persisted
- paper lifecycle persists a paper position and later a paper trade

## 5. Commission training

This section matters. Entering the wrong commission value will distort paper
results badly.

### Equity vs options commission

- `commission_per_trade` is the equity paper-trade fee setting
- `commission_per_contract` is the options paper-lifecycle fee setting
- they are separate and must not be treated as interchangeable

### Options commission rule

Options commission is:

`commission_per_contract x contracts x legs x events`

Where:

- `contracts` = option contracts, not shares
- `legs` = each option leg in the structure
- `events` = usually open and close

Important:

- do **not** multiply options commission by `100`
- the `100` contract multiplier applies to premium and P&L math only
- it does **not** apply to broker commission modeling

### Example

`$0.65 x 1 contract x 4 legs x 2 events = $5.20 total commission`

### Why this matters

If you enter `$65` instead of `$0.65`, your fee modeling is wrong by `100x`.

That means the same 1-contract, 4-leg, open+close example becomes:

`$65 x 1 x 4 x 2 = $520`

That would badly distort net P&L and make paper results look far worse than
they actually are.

## 6. Provider and data access

Provider health is an operator trust screen, not a live-trading enablement
screen.

Use it to answer:

- are providers configured?
- is the workflow using provider bars or explicit fallback?
- is a workflow blocked because provider data is unavailable?

Practical operator notes:

- SPX and NDX may require index-data entitlement
- if index access is unavailable, SPY and QQQ are practical ETF substitutes
  for research and workflow testing
- options chain rows, Greeks, IV, and open interest depend on provider plan
  coverage
- missing options data is often a provider/plan limitation unless the app
  explicitly shows a different error
- the Recommendations options risk surface and Analysis options preview now
  repeat workflow source, chain source/as-of, and Expected Range provenance
  when available; missing values should render as `Source unavailable` or
  `As-of unavailable`, not as a hidden zero or silent success
- durable Orders paper-options rows may not include full provider/source
  metadata yet; use the research preview for chain source/as-of context

Interpretation rule:

- provider readiness does **not** mean live trading is enabled
- provider degradation should be treated as a workflow trust issue first

## 7. Symbol discovery and watchlists

Current symbol and watchlist management is still intentionally simple. You may
need to know the symbols you want to inspect and, in scheduled-report contexts,
manage symbol lists manually.

Future roadmap work is planned for better recommendation-universe management:

- search by ticker and company/security name
- user-scoped watchlists with searchable/sortable tables
- add/delete individual symbols and bulk add/import
- duplicate handling and active/inactive symbols
- optional groups such as `Core`, `ETFs`, `Tech`, `Options Candidates`, and
  `Watch Only`
- provider/source support labels when available
- ETF/index substitution guidance such as `SPX` / `NDX` versus `SPY` / `QQQ`

This future work is not trade execution. Provider support labels and options
eligibility are research context only, and missing metadata should not block
manual symbol entry.

## 8. Metric glossary and tooltips

The console currently exposes operator abbreviations and risk terms such as
`RR`, `CONF`, `Score`, `DTE`, Expected Range, `IV`, open interest, breakevens,
gross/net P&L, commissions, Provider readiness, Paper lifecycle, and Replay
payoff preview.

The first glossary foundation is now in place: a shared registry and reusable
metric-help component can provide small in-context help icons with accessible
click/tap explanations. The rollout currently covers commission settings,
Expected Range labels, Provider readiness context, and the most visible
Recommendations score/risk labels such as `Score`, `RR`, `CONF`, max
profit/loss, breakevens, gross/net P&L, and options commissions. Orders now
also has compact help on the main P&L and commission labels for equity paper
records and durable paper-options rows. Analysis and Replay now have compact
help on the most relevant options risk/source, score/confidence, P&L, and fee
labels. The current in-context glossary/tooltips rollout is now closed for
those surfaces; a broader glossary/reference page remains future work.

Important interpretation rules:

- `CONF` and `Score` are not probability of profit.
- Expected Range is research context and does not change payoff math.
- Provider readiness does not mean live routing or execution.
- Paper lifecycle means persisted paper records, not broker orders.
- Equity commission per trade and options commission per contract are
  different settings.

Longer explanations should continue to live in operator docs so dense tables
and cards stay readable.

## 9. Chart and indicator training

Analysis and Recommendations now use compact workflow chart presets.

Presets:

- `Clean`
- `Trend`
- `Momentum`
- `Volatility`
- `All`

How to read them:

- the main **price panel** carries price and overlays
- the **volume panel** is separate from price
- the **RSI panel** is separate from price and stays on a 0-100 scale
- the hover snapshot synchronizes across the visible panels

Operator guidance:

- use `Clean` for a simple price + volume view
- use `Trend` when you want moving-average context
- use `Momentum` when you want RSI context
- use `Volatility` when you want Bollinger / expected-range context where
  available
- use `All` only when you need the denser research view

Indicators are research context only. They are not automatic trade
instructions.

## 10. Expected Move / Expected Range

Expected Move / Expected Range is a first-class options research concept in
MacMarket-Trader.

What it is:

- contextual research information
- a framing tool for the current options setup
- a way to understand whether the structure sits inside or outside the
  currently estimated move

What it is not:

- it does not change payoff-at-expiration math
- it does not approve execution
- it is not a recommendation by itself

Expected range states:

- `computed`
- `blocked`
- `omitted`

Operator rule:

- blocked or omitted states should show a reason
- missing expected range should be read as `Unavailable` or muted context, not
  as a hidden zero
- the `Structure risk` card may repeat Expected Range status and reason, but
  it still remains research context only
- the Recommendations `Structure risk` card now includes a compact Expected
  Range visualization when lower/upper bounds are available
- missing or blocked Expected Range visualization should still read as
  `Unavailable` or muted context, not as a hidden zero

## 11. Safety guardrails

Treat these as hard boundaries:

- paper-only
- no live routing
- no staged real brokerage orders
- no assignment/exercise automation
- no naked short options in the early options lifecycle
- options lifecycle remains separate from equity lifecycle
- expected range or replay payoff preview is not a recommendation by itself
- provider health is not execution approval

Also remember:

- equities and options are intentionally mode-separated
- options do not reuse equity replay persistence or equity order semantics
- if a screen says paper-only, believe it

## 12. Manual smoke checklist

Use this checklist when validating the current operator workflow:

1. Verify **Provider Health** and confirm the workflow source is truthful.
2. Open **Settings** and set:
   - equity `commission_per_trade`
   - options `commission_per_contract`
3. Run an **equity** setup through Analysis.
4. Run an **options** setup and review research preview details.
5. Run **Replay payoff preview** for the options structure.
6. Open the **paper option structure** from Recommendations.
7. Manually close it with one exit premium per leg.
8. Verify:
   - gross P&L
   - opening commissions
   - closing commissions
   - total commissions
   - net P&L
9. Confirm no live-trading or brokerage-routing language appears.

## 13. Troubleshooting

### "Data not available on current plan"

Usually this means provider entitlement, not a trade-logic error.

Check:

- Provider Health
- current symbol type
- current provider plan coverage

### SPX / NDX not loading cleanly

Try:

- `SPY` instead of `SPX`
- `QQQ` instead of `NDX`

That gives you practical ETF substitutes when index plan access is missing.

### Missing option chain

Possible causes:

- provider plan does not expose the needed chain data
- the symbol/expiration is not currently available
- the app has enough structure context to show research but not enough chain
  detail to show preview rows

### Missing expected range

Possible causes:

- IV snapshot unavailable
- chain data missing
- method blocked or omitted

This does not automatically mean the rest of the research setup is invalid.

### Preview blocked / unsupported

Likely causes:

- incomplete legs
- missing premium assumptions
- unsupported structure type
- naked short structure
- multi-expiration structure

Read the blocked reason directly. Do not infer.

### Close blocked because already closed

The current manual-close path blocks double close. If the position is already
closed, that is expected behavior, not a hidden failure.

### Wrong commission amount entered

If net P&L looks wildly wrong:

1. check `commission_per_contract`
2. confirm it is something like `0.65`, not `65`
3. remember options commission is not multiplied by `100`

## 14. Current phase status

Current project status, in operator terms:

- Phase 7 is closed for the equity paper-readiness scope
- Phase 8A complete
- Phase 8B complete
- Phase 8C complete
- Phase 8D complete for the current paper-options lifecycle scope
- Phase 8E complete for the current Recommendations options risk/operator UX
  scope
- Phase 8F complete: final closure for the current scoped paper-first options
  capability
- Phase 8 is closed for the current scoped paper-first options capability
- Phase 9A complete: options operator parity and data-quality planning
- Phase 9B complete: durable paper-options Orders/Positions visibility
- Phase 9C1 complete: initial provider/source/as-of parity for Analysis,
  Orders durable paper-options rows, and Provider Health copy
- Phase 9C complete: current provider/source/as-of parity scope is closed
  across Analysis, Recommendations, Orders durable paper-options rows,
  Provider Health, and operator guidance
- Phase 9D1 complete: advanced Expected Move / Expected Range visualization
  design checkpoint
- Phase 9D2 complete: reusable Expected Range visualization component with
  first Recommendations integration
- Phase 9D complete: current Recommendations Expected Range visualization
  scope is closed
- Phase 9 complete: current options operator parity, provider/source/as-of,
  and Recommendations Expected Range visualization scope is closed
- Phase 10 planning started: remaining options/provider/crypto work is being
  organized into safe polish, design checkpoints, and explicitly later
  implementation tracks
- Phase 10A1 complete: Analysis now includes the compact Expected Range
  visualization for options research setups using existing setup fields only
- Phase 10B1 complete: Orders durable paper-options rows are easier to scan as
  display-only paper lifecycle records using existing persisted fields only
- Future workflow polish added: symbol discovery and user-scoped watchlist
  management is planned for recommendation-universe management, not execution
- Future workflow polish added: operator glossary and explainable metric
  tooltips are now started with the `10C1` shared glossary foundation,
  `10C2` Recommendations score/risk-label rollout, `10C3` Orders
  P&L/commission-label rollout, `10C4` Analysis/Replay label rollout, and
  `10C5` closure audit for the current in-context scope; the optional
  reference-page rollout remains future work and does not change
  scoring, probability, provider, execution, replay behavior, payoff,
  lifecycle, or commission behavior

Current options boundary:

- research preview is live
- replay payoff preview is live
- paper open/manual-close lifecycle is live
- Orders now provides durable paper-options position/trade visibility outside
  Recommendations
- current scoped Phase 8 paper-first options capability is complete
- current scoped Phase 9 operator parity and Expected Range visualization
  capability is complete
- Phase 10 does not enable backend runtime behavior; `10A1` adds the optional
  Analysis Expected Range visualization using existing fields only
- `10B1` improves Orders display/readability for saved and manually closed
  paper option lifecycle rows without adding Orders actions
- expiration settlement is still deferred
- broader options dashboard depth and workflow actions remain deferred
- persisted options recommendations, options replay persistence,
  assignment/exercise automation, naked shorts, probability/margin modeling,
  crypto implementation, and live routing remain future work

## Final operator reminder

MacMarket-Trader is designed to help you think and verify, not to replace
judgment.

Use it to:

- inspect the setup
- validate the workflow source
- compare gross vs fee-aware net results
- keep research, replay, and paper lifecycle roles separate

Do not use it as proof that a trade should exist just because a preview or
paper result looks attractive.
