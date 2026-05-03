# MacMarket-Trader Operator Welcome Guide

Last updated: 2026-05-03

This is the practical welcome/training guide for MacMarket-Trader operators.
It is written for:

- the operator using the console day to day
- the project owner learning or demoing the system
- future AI/Codex agents that need accurate high-level usage context

MacMarket-Trader is still paper-only. Nothing in this guide authorizes live
trading, brokerage routing, or real-money execution.

## MacMarket Quick Start

### What this is

MacMarket is a research and paper-trading console. It has no live trading,
no broker routing, and no real-money execution.

### Daily workflow

1. Check **Provider Health**.
2. Check **Market Risk Today**.
3. Review **Charts** and **Analysis**.
4. Refresh the **Recommendations** queue.
5. Compare candidates with **Opportunity Intelligence**.
6. Promote only candidates worth tracking.
7. Stage a paper order with risk-at-stop and max paper order value checks.
8. Manage open positions from **Orders** and **Active Position Review**.

### Equity paper

Risk budget at stop controls the estimated max loss for a paper order. Max
paper order value caps the dollars committed to that staged paper order.

### Options paper

Options research preview is read-only. The options paper lifecycle is
persisted once you intentionally save a supported structure. Option marks
require provider entitlement; `mark_unavailable` means MacMarket did not fake
option P&L.

### LLM

Opportunity Intelligence and OpenAI-backed explanations compare and explain
only. Deterministic engines own approval, entry, stop, target, sizing, risk
gates, and paper order creation.

### Safety rules

No live trading. No broker routing. No automatic exits. No automatic rolls.
No automatic adjustments. No automatic exercise or assignment.

### Red flags

Provider degraded, stale data, risk-calendar `restricted` or `no_trade`,
option mark unavailable, missing lineage, or missing evidence.

### Where to go

Dashboard, Charts, Analysis, Recommendations, Orders, Provider Health, and
Settings.

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
  - Options Position Review with provider marks when entitled
  - deterministic expiration, assignment-risk, exercise-risk, and paper
    settlement review
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
| Options research preview | Shows structure, legs, expiration/DTE, expected range status, chain preview when available, and chart/research context | Not execution support |
| Options replay payoff preview | Read-only, non-persisted expiration payoff preview for supported defined-risk structures | Does not create replay runs, orders, positions, or trades |
| Paper options lifecycle | Persists a paper-only options position and supports manual close for supported structures | No live routing, no automatic exits, no automatic rolls |
| Options Position Review | Reviews open options paper structures, option marks when entitled, DTE, moneyness, assignment/exercise risk, and paper-only settlement preview when available | No automated exercise, assignment, close, roll, adjustment, or broker order |
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
   Intraday 1H/4H charts are regular-trading-hours normalized.
5. Continue based on mode.

### Equities flow

1. In Analysis, review the setup and chart.
2. Check the Market Risk Calendar and sit-out guardrails.
3. Create the recommendation.
4. Open **Recommendations**, refresh the ranked queue, and review persisted
   lineage.
5. Use Opportunity Intelligence to compare selected queue candidates when
   OpenAI is configured; deterministic ranking and approval still own the
   trade fields.
6. Run **Replay** to validate the path.
7. If the replay is stageable, continue into **Orders**.
8. Stage the paper order with risk budget at stop and max paper order value
   checks.
9. Use **Active Position Review** for open equity paper positions, including
   already-open awareness when the same symbol reappears in Recommendations.
10. Close manually when ready and review realized paper results.

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
8. Use **Options Position Review** in Orders for open structures, mark status,
   expiration status, assignment/exercise risk, and paper-only settlement
   review.

## 4. Options training

Keep these distinctions clear:

- **Options research preview** is not execution support.
- **Replay payoff preview** is read-only and non-persisted.
- **Paper option lifecycle** creates persisted paper-only option positions and
  trades for the currently supported lifecycle scope.
- **Save as paper option position** means a paper-only record is created.
  No broker order is sent.
- **Manual close** requires one exit premium per leg.
- **Expiration settlement review** is deterministic and paper-only.
- **Settle paper expiration** requires explicit manual confirmation when it is
  available.
- **Assignment/exercise risk** is informational only.
- **Assignment/exercise automation** is not available.
- **Naked shorts** are blocked.
- **Live routing** is not available.
- **Provider option marks** depend on Polygon/Massive option snapshot
  entitlement. If the provider returns `Not entitled to this data`, MacMarket
  shows `mark_unavailable` and does not fabricate leg marks or P&L.

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
- options chain rows, option snapshot marks, Greeks, IV, and open interest
  depend on provider plan coverage
- Provider Health can honestly show `options_data` as degraded when
  Polygon/Massive says `Not entitled to this data`; that means option marks
  are unavailable, not that live trading is enabled or disabled
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

## 7. Admin evidence and release gates

Admins and maintainers can use the release/evidence tooling to collect
readiness artifacts before deploy or diligence review.

Useful local commands:

```powershell
python scripts/run_release_gate.py --quick
python scripts/run_release_gate.py
python scripts/generate_release_evidence.py
```

`--quick` prints progress for scans, targeted compliance evidence tests, clean
archive dry-run, and evidence generation. The full release gate adds backend
tests, frontend tests, TypeScript, and npm audit report-only. These gates are
evidence and deployment hygiene tools; they do not call live brokers or enable
trading.

## 8. Symbol discovery and watchlists

Current symbol and watchlist management is improved but still intentionally
manual. You may need to know the symbols you want to inspect and, in
scheduled-report contexts, manage symbol lists yourself.

Current manual list entry accepts tickers separated by commas, spaces, tabs, or
new lines, then shows a parsed uppercase preview and duplicate feedback before
you refresh a Recommendations queue or save a schedule/watchlist list. When
editing a watchlist, you can replace the saved list or add unique pasted
symbols to the existing list while keeping existing symbols first. Use
`SPY` / `QQQ` as ETF substitutes when index data for `SPX` / `NDX` is
unavailable.

Current watchlist and universe-selection improvements:

- current watchlists are user-scoped named symbol lists
- the Schedules Watchlists card can search/sort saved lists, show symbol
  counts, show normalized symbol chips, filter within a list, and remove
  individual chips through the existing watchlist update path
- watchlist editing supports **Replace current symbols** or **Add to existing
  symbols**
- a protected read-only symbol-universe preview API can resolve manual,
  watchlist, watchlist-plus-manual, all-active, and mixed inputs without
  submitting Recommendations, mutating schedules/watchlists, or calling
  providers
- Recommendations now has a preview-only universe selector for manual,
  watchlist, watchlist-plus-manual, and all-active sources; use **Use resolved
  symbols** to copy preview output into the existing manual input before
  refreshing the queue
- Schedules now has a preview-only universe selector for the same sources; use
  **Use resolved symbols in this schedule** to copy preview output into the
  existing schedule symbol field, then save explicitly with Create or Update
  selected
- schedules use static symbol snapshots; later watchlist edits do not
  automatically change existing schedules

Future roadmap work is still planned for richer recommendation-universe
management:

- search by ticker and company/security name
- normalized symbol-universe production UI
- richer import audit
- active/inactive symbols in production watchlist workflows
- optional groups such as `Core`, `ETFs`, `Tech`, `Options Candidates`, and
  `Watch Only`
- provider/source support labels when available
- provider-backed symbol discovery/search
- tags/groups selector behavior
- dynamic watchlist refresh for schedules only if separately approved later
- ETF/index substitution guidance such as `SPX` / `NDX` versus `SPY` / `QQQ`

This future work is not trade execution. Provider support labels and options
eligibility are research context only, and missing metadata should not block
manual symbol entry.

Design checkpoint status:

- the current-state inventory and future implementation plan now live in
  `docs/symbol-watchlist-design.md`
- the roadmap is following a hybrid path: keep current watchlist compatibility
  while adding dedicated user-symbol universe / watchlist membership
  foundations for later production UI
- the current comma-entry cleanup, current watchlist table polish, and bulk
  duplicate-handling slices are complete; recommendation/schedule
  universe-selection design is documented; the read-only preview API and
  Recommendations and Schedules preview/apply selectors plus closure audit are
  complete for the current scope;
  provider-backed search, normalized symbol-universe production UI, import
  audit, and dynamic watchlist refresh remain future work
- the additive `user_symbol_universe` plus `watchlist_symbols` schema
  foundation and internal repository/resolver foundation now exist, but current
  Recommendation and Schedule production flows still use the existing symbol
  arrays for compatibility
- the universe-selection checkpoint recommends static resolved schedule
  snapshots by default so future schedule runs do not unexpectedly change when
  watchlists change
- schedule universe preview/apply now follows that rule: later watchlist edits
  do not automatically change existing schedules

## 9. Metric glossary and tooltips

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

## 10. Chart and indicator training

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

## 11. Expected Move / Expected Range

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

## 12. Safety guardrails

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

## 13. Manual smoke checklist

Use this checklist when validating the current operator workflow:

1. Verify **Provider Health** and confirm the workflow source is truthful.
2. Open **Settings** and set:
   - equity `commission_per_trade`
   - options `commission_per_contract`
3. Run an **equity** setup through Analysis.
4. Refresh **Recommendations** and confirm queue/source/risk labels are clear.
5. Stage an equity paper order and verify risk-at-stop plus max paper order
   value checks.
6. Open **Orders** and verify **Active Position Review** shows open equity
   paper positions without automatic exits.
7. Run an **options** setup and review research preview details.
8. Run **Replay payoff preview** for the options structure.
9. Open the **paper option structure** from Recommendations.
10. Open **Orders** and verify **Options Position Review** shows mark status,
    DTE, assignment/exercise risk, and no automatic roll/adjust/exercise
    action.
11. Manually close it with one exit premium per leg.
12. Verify:
   - gross P&L
   - opening commissions
   - closing commissions
   - total commissions
   - net P&L
13. Confirm no live-trading or brokerage-routing language appears.

## 14. Troubleshooting

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

### Option mark unavailable

Possible causes:

- provider plan is not entitled to option snapshot data
- the specific option contract snapshot is unavailable
- the snapshot is stale or missing bid/ask/last fields

This is expected to render as `mark_unavailable`. Do not treat it as zero
premium, zero P&L, or permission to fabricate a mark.

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

## 15. Current phase status

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
- Symbol/watchlist design checkpoint complete: current watchlists are still
  simple user-scoped named symbol lists, while the future plan recommends a
  hybrid user-symbol universe model before richer implementation
- Phase 10W2 complete: current manual symbol entry on Recommendations,
  Schedules, and watchlist editing now has clearer helper copy, parsed
  uppercase previews, duplicate feedback, and SPX/NDX versus SPY/QQQ guidance
  without changing backend storage, provider search, or recommendation behavior
- Phase 10W3 complete as a design checkpoint: future symbol-universe schema
  planning now covers user-scoped canonical symbol rows, watchlist membership,
  compatibility snapshots, resolver behavior, migration/backfill, and rollback
  without implementing schema or runtime changes
- Phase 10W4 complete: additive `user_symbol_universe` and
  `watchlist_symbols` schema foundations exist for future normalized symbol
  workflows, while current watchlist JSON storage, schedule payload symbols,
  recommendation generation, provider behavior, and frontend UI remain
  compatible
- Phase 10W5 complete: internal repository/read-model and resolver helpers can
  normalize, dedupe, combine, pin, exclude, and user-scope future symbol
  universe inputs, but production Recommendations and Schedules are not wired
  to replace their current symbol-array behavior
- Phase 10W6 complete: the current Schedules Watchlists card now supports
  search/sort, symbol counts, normalized chips, per-list symbol filtering,
  duplicate feedback, and per-symbol removal using the existing watchlist update
  route while preserving current JSON storage and schedule payload behavior
- Phase 10W7 complete: watchlist edits now make replace versus add-to-existing
  explicit for pasted symbols, preserve existing symbols first when merging,
  append new unique symbols in pasted order, and report duplicates before
  saving the same current symbol-array shape
- Phase 10W8 complete as a design checkpoint: future Recommendations and
  Schedules universe selectors should resolve manual, watchlist, all-active,
  tags/groups, exclusions, and pinned symbols into previewed symbol arrays
  before submit, with static schedule snapshots as the default
- Phase 10W8A complete: a protected read-only backend preview route can resolve
  manual, watchlist, watchlist-plus-manual, all-active, and mixed symbol
  universe inputs without submitting Recommendations, mutating schedules or
  watchlists, calling providers, or implying execution
- Phase 10W8B complete: Recommendations now has a preview-only universe
  selector that can resolve manual, saved-watchlist, watchlist-plus-manual, and
  all-active sources and explicitly copy resolved symbols into the existing
  manual queue input without changing recommendation generation or schedule
  behavior
- Phase 10W8C complete: Schedules now has a preview-only universe selector that
  can copy resolved symbols into the existing schedule symbol input as a static
  snapshot without changing schedule execution or enabling dynamic watchlist
  refresh
- Phase 10W8D complete: recommendation/schedule universe-selection closure
  confirmed the preview API remains read-only/no-mutation and the
  Recommendations and Schedules selectors remain preview/apply only, with queue
  submit and schedule save/run behavior unchanged
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
- Options Position Review is live for open options paper structures
- provider-backed option marks populate review only when provider entitlement
  permits snapshots
- expiration, moneyness, assignment-risk, exercise-risk, and paper-only
  settlement review are live
- manual paper expiration settlement requires explicit confirmation when an
  expired structure has a usable underlying mark
- current scoped Phase 8 paper-first options capability is complete
- current scoped Phase 9 operator parity and Expected Range visualization
  capability is complete
- Phase 10 does not enable backend runtime behavior; `10A1` adds the optional
  Analysis Expected Range visualization using existing fields only
- `10B1` improves Orders display/readability for saved and manually closed
  paper option lifecycle rows without adding Orders actions
- automatic expiration settlement is not available
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
