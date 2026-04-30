# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-04-30

## Positioning
MacMarket-Trader is positioned as an invite-only, operator-grade trading
intelligence console — not "another charting page." The defensible edge is
strategy-aware analysis, event + regime context, explicit trade levels,
replay before paper execution, recurring ranked trade reports, and
explainable AI layered on top of deterministic logic. **It is paper-only.**

## Current Status
Phases 0–6 and Pass 4 complete. Three alpha users (admin + 2 approved).
Deployed at https://macmarket.io via Cloudflare Tunnel.
Tests: pytest 210, vitest 170, Playwright 31. tsc clean.
Phase 7 is complete for the current equity/paper-readiness foundation.
Phase 8C is complete for the current read-only, non-persisted options replay
preview scope.
Phase 8D is complete for the current paper-only manual-close options paper
lifecycle scope, including dedicated persistence, repository/service
contracts, open/manual-close behavior, contract-commission net P&L, frontend
operator UI, and closure audit/docs alignment.
Phase 8E1 is complete for the current operator risk-summary foundation on the
Recommendations options research surface.
Phase 8E2 is complete for the current Recommendations options provider/source,
as-of, and data-quality warning coverage.
Phase 8E3 is complete for the current guided Recommendations options workflow
UX.
Phase 8E is complete for the current Recommendations options risk/operator UX
surface only.
Post-8E smoke-test polish clarified reference-only chain-preview data
availability and Step 5 paper-close-result wording on Recommendations without
moving beyond the scoped paper-first options capability.
Phase 8F is complete, and Phase 8 is now closed for the current scoped
paper-first options capability only. Follow-on provider/source parity and the
Recommendations Expected Range visualization are now covered by the closed
Phase 9 current scope.
Phase 9A planning is complete for options operator parity and data-quality
hardening. Phase 9B is complete for durable paper-options Orders/Positions
visibility. Phase 9C is complete for the current provider/source/as-of parity
scope across Analysis, Recommendations, Orders durable paper-options rows,
Provider Health, and operator guidance using existing payload fields only.
Phase 9D is complete for the current Recommendations Expected Range
visualization scope. Analysis integration later landed in `10A1`; future
provider-depth, live routing, expiration settlement, assignment/exercise, and
probability modeling remain deferred. Phase 9 is closed for the current
options operator parity, source/as-of, and Expected Range visualization scope.
Phase 10 planning is now open as a deferred-work sequencing track. `10A1` is
complete for the frontend-only Analysis Expected Range visualization reuse,
and `10B1` is complete for frontend-only Orders display/readability polish on
durable paper-options lifecycle rows. `10C1` is complete for the first
frontend-only explainable metric UX foundation: central glossary registry,
reusable metric-help component, and narrow Settings / Expected Range /
Provider Health integrations. `10C2` is complete for compact Recommendations
score/risk-label help using the existing glossary and `MetricLabel`
component. Remaining Phase 10 slices stay open.
The track defines safe near-term options polish, medium-risk design
checkpoints, and explicitly later execution/crypto work without moving backend
runtime behavior. Future symbol discovery and watchlist management is now
tracked as a recommendation-universe workflow item, not trade execution or
broker routing. Future operator glossary and explainable metric tooltips are
now tracked as workflow comprehension polish, not changes to scoring,
probability modeling, provider behavior, or execution semantics.
Phase 8 options hardening micro-pass preserved the scoped paper-only options
boundary and recorded that CLAUDE.md test context is now aligned to the
current vitest 160 count,
API-level iron condor open/close lifecycle coverage was added, expiration
settlement rejection coverage was added, the `opening_commissions`
reconstruction limitation was documented, and the dead `opening_commissions`
branch was removed without adding feature, schema, UI, replay,
recommendation, or brokerage behavior.

## Completed Phases

### Phase 0 — Foundation
- Repo structure, FastAPI backend, Next.js 15 frontend, SQLite DB
- Clerk auth integration, local DB approval layer, audit logging
- `deploy_windows.bat` mirror + test pipeline + Windows Task Scheduler

### Phase 1 — Core workflow
- Analyze → Recommendation → Replay → Paper Order workflow
- Deterministic recommendation engine with explicit entry / stop / target levels
- Replay engine: historical bar walk, fill simulation, step logging, equity curve
- WorkflowBanner, guided mode, explorer mode, lineage threading via URL params

### Phase 2 — Identity + auth
- Invite-only onboarding, approval gate, role system (admin / user)
- Identity reconciliation: `invited::email` row → real Clerk sub on first sign-in
- Admin panel: pending users, invite create/resend/revoke, provider health
- Branded transactional emails (invite, approval, rejection) with inlined logo

### Phase 3 — Market data + providers
- Polygon market data integration (quotes, bars, news, options chain preview)
- Provider/fallback truth model with health indicators on dashboard + admin
- `WORKFLOW_DEMO_FALLBACK` for dev/demo deterministic-bar mode
- Index symbol normalization, `SymbolNotFoundError`, `DataNotEntitledError` handling

### Phase 4 — Recommendations + replay
- Recommendation queue with promote/make-active and save-as-alternative actions
- Replay validation gate: `has_stageable_candidate` blocks paper-order staging
- Strategy registry with regime-aware scoring + per-strategy hint copy
- Ranked queue → recommendation → replay → order lineage with full audit trail

### Phase 5 — Operator console polish
- Guided mode: sticky Active Trade banner, auto-advance CTAs, WorkflowBanner chips
- TopbarContext, strategy selector hints, role-conditional sidebar, brand pre-auth
- Pulsing primary CTA states ("Run replay now" → "Run again"), readable lineage
- Welcome guide page at `/welcome` rendered from `docs/alpha-user-welcome.md`
- 26 Playwright e2e tests gating guided workflow

### Phase 6 — Close-trade lifecycle + Pass 4
- Open positions list, inline close ticket, closed-trades blotter, realized P&L
- Cancel staged order, reopen closed position (5-minute undo window) + audit log
- `display_id` on recommendations (e.g. `AAPL-EVCONT-20260429-0830`) everywhere
  rec ID appears, with `Rec #shortid` fallback for legacy rows
- Per-user `risk_dollars_per_trade` override + Settings page at `/settings`
- Invite email with welcome-guide CTA + sign-in CTA (terse copy, two buttons)
- Timezone-aware schedule display ("08:30 AM ET — Indianapolis · 9:30 AM your time")
- 31 Playwright e2e gates, 99 frontend helper tests at Phase 6 close, 210 backend pytest gates

## Phase 7 Closeout + Upcoming Phases

### Phase 7A — Commission-aware realized paper P&L
- Complete for current equity/paper scope:
  `gross_pnl` / `net_pnl` split in `paper_trades`
- Complete for current equity/paper scope:
  per-trade equity commission (default `$0`) applied to realized paper close
  math
- Complete for current equity/paper scope:
  commission settings exposed in user Settings page
- Complete for current equity/paper scope:
  backend fields on `paper_trades` and per-user `commission_per_trade` /
  `commission_per_contract` on `app_users` with env fallback defaults
- Complete for current equity/paper scope:
  `realized_pnl` remains preserved as a back-compat alias to net P&L where
  legacy rows or older consumers still expect that field

### Phase 7B — Equity fee previews / projected net paper outcomes
- Complete for current equity/paper scope:
  replay / order / open-position operator surfaces show explicit equity-only
  fee estimates
- Complete for current equity/paper scope:
  projected net outcome is shown only when projected gross can be derived
  safely from existing recommendation levels
- Complete for current equity/paper scope:
  round-trip preview copy explicitly labels lifecycle estimates as `entry + exit`
- Complete for current equity/paper scope:
  close previews explicitly label fee estimates as `close-only`
- Complete for current equity/paper scope:
  unavailable projected gross/net values render as `Unavailable` rather than
  `0`, `NaN`, `undefined`, or `null`
- Note:
  current fee-preview math lives in `admin.py` for speed and reviewability;
  centralizing fee math into a dedicated module can happen in a later cleanup
  slice if Phase 7 grows further

### Phase 7C — Provider health + operator readiness
- Complete for current paper/provider-readiness scope:
  Admin / Provider Health now surfaces explicit Alpaca paper-provider
  readiness, including selected mode, configuration presence, and paper-only
  readiness framing without exposing secrets
- Complete for current paper/provider-readiness scope:
  FRED and news readiness now appear alongside existing auth, email, and
  market-data health so operators can verify macro/news context inputs
  explicitly
- Complete for current paper/provider-readiness scope:
  provider-health is framed as a pre-provider-expansion operator-readiness
  gate, not live-trading enablement
- Complete for current paper/provider-readiness scope:
  config-only providers clearly distinguish `Configured` from `OK` and show
  `Probe unavailable` when no dedicated safe live probe exists
- Note:
  FRED/news readiness is currently configuration-first and marks live probe
  status as unavailable where no dedicated safe lightweight probe exists yet
- Note:
  market-data workflow mode, fallback/blocking behavior, latency, and sample
  symbol remain the source-of-truth provider health contract for
  recommendation/replay/orders workflow trust

### Phase 7D — Closure criteria / remaining cleanup
- Complete for current equity/paper-readiness scope:
  roadmap/status wording has been cleaned up to match the implemented Phase 7
  slices without overstating live-provider or options support
- Complete for current equity/paper-readiness scope:
  provider-readiness language is clarified so config-only providers do not
  imply successful live upstream probe health
- Complete for current equity/paper-readiness scope:
  duplicate `.gitignore` cleanup is complete
- Complete for current equity/paper-readiness scope:
  Phase 7 test files are tracked and named clearly

### Phase 7 Closure Note
- Phase 7 is complete for the current equity/paper-readiness foundation.
- Remaining deferred items are intentionally moved to later phases and should
  not block Phase 8 planning.

## Deferred From Phase 7

- `commission_per_contract` is stored and exposed, but options application is
  deferred to Phase 8 / options-fee parity work
- options-fee parity is deferred to Phase 8 / options
- broader fee modeling is deferred:
  per-share fees, regulatory fees, borrow / locate assumptions, and richer
  unrealized net P&L assumptions remain outside the current Phase 7 scope
- FRED/news dedicated safe live probes are deferred until later
  provider-depth work; current Phase 7 scope covers configuration/readiness
  visibility only
- Alpaca readiness remains paper/provider-readiness only, not live routing or
  brokerage enablement

### Phase 8 — Options research → paper parity
- Status:
  `8A` complete, `8B` complete for the current non-persisted research-only
  scope, `8C` complete for the current read-only, non-persisted
  replay-preview scope, `8D1` / `8D2` / `8D3` / `8D4` / `8D5` / `8D6` /
  `8D7` / `8D8` complete for design, schema, repository/service contracts,
  open/manual-close paper lifecycle behavior, contract-commission net-P&L
  modeling, frontend operator UI, and closure audit/docs alignment. `8E` and
  `8F` are now complete for the current scoped paper-first options capability. Dedicated
  options persistence tables, internal repository contracts, and open/manual
  close paper lifecycle paths now exist, the manual-close path now stores
  contract-commission-aware net P&L, and Recommendations now hosts a
  paper-only operator UI for open/manual-close workflows, while expiration
  settlement, broader provider/source parity across additional options
  surfaces, and execution-enablement changes remain deferred.
- Master plan:
  [options-architecture.md](options-architecture.md)
- Companion docs:
  [options-replay-design.md](options-replay-design.md),
  [options-paper-lifecycle-design.md](options-paper-lifecycle-design.md),
  [options-risk-ux-design.md](options-risk-ux-design.md),
  [options-test-plan.md](options-test-plan.md)
- 8A status:
  complete
- 8A acceptance:
  options scope, guardrails, repo anchors, and implementation sequence are
  documented without changing runtime behavior
- 8B status:
  complete for the current non-persisted research-visibility scope
- 8B acceptance:
  Analysis / Recommendations expose read-only options research safely, keep
  queue/promote/replay/order/staging CTAs suppressed, and render expected
  range, chain-preview, and missing-data states safely
- 8B not included:
  persisted options recommendations, options replay, options orders, options
  fills, options positions, and options trades
- 8C status:
  complete for the current read-only, non-persisted replay-preview scope
- 8C acceptance:
  supported defined-risk options structures can be previewed through
  deterministic expiration-payoff math plus a read-only operator UI, while
  equity replay behavior remains untouched and Expected Move / Expected Range
  stays contextual rather than modifying payoff math
- 8C implemented now:
  isolated pure payoff math helpers plus a dedicated read-only options replay
  preview contract at `POST /user/options/replay-preview`, with focused backend
  tests for long-option primitives, vertical debit spreads, iron condor,
  blocked invalid/naked-short payloads, explicit non-persistence, and a
  Recommendations-side operator payoff preview UI with compact summary and
  expiration payoff table; the surrounding options research preview continues
  to carry Expected Move / Expected Range context with safe blocked/omitted
  reasons and explicit research-only labeling
- 8C must not change:
  current equity `ReplayEngine`, equity replay persistence semantics, equity
  `RecommendationService.generate()` behavior, or equity order/fill semantics
- 8C not included:
  staged options orders, options positions/trades, mark-to-market parity,
  assignment/exercise automation, advanced Expected Move / Expected Range
  visualization beyond the current contextual summary, or live routing
- 8D status:
  `8D1` design checkpoint, `8D2` schema/migration foundation, `8D3`
  repository/service contracts, `8D4` open paper option structure behavior,
  `8D5` manual close paper option structure behavior, `8D6`
  `commission_per_contract` net-P&L modeling, `8D7` frontend operator UI,
  and `8D8` closure audit/docs alignment are complete for the current
  paper-only manual-close scope
- 8D acceptance target:
  supported defined-risk structures can move through an options-specific paper
  lifecycle with explicit leg summaries, contract-multiplier math,
  `commission_per_contract`, and gross/net realized P&L, without contaminating
  current equity paper lifecycle
- 8D implemented now:
  dedicated `paper_option_orders`, `paper_option_order_legs`,
  `paper_option_positions`, `paper_option_position_legs`,
  `paper_option_trades`, and `paper_option_trade_legs` tables now exist in ORM
  metadata and Alembic, with separate header/leg persistence, JSON
  breakevens, `execution_enabled=false` defaults on option paper orders, a
  `prepare_option_paper_structure(...)` validation helper, and an
  `OptionPaperRepository` for typed create/fetch contracts with focused schema
  plus repository tests; supported defined-risk structures can now open
  through a dedicated paper-only backend path at
  `POST /user/options/paper-structures/open`, which creates options-specific
  order and position headers plus legs without creating equity orders, replay
  runs, or recommendation rows and now exposes opening paper contract
  commissions; open positions can now close manually through
  `POST /user/options/paper-structures/{position_id}/close`, which writes
  options-specific trade headers plus legs, persists gross/net P&L plus
  total contract commissions, and keeps current equity write tables, routes,
  and replay/order behavior untouched; Recommendations now hosts a separate
  paper-only options lifecycle panel with same-origin open/close proxies,
  explicit commission-per-contract formula guidance, estimated opening/open +
  close commission visibility, in-memory manual close inputs/results for
  the newly opened position only, and closure-reviewed operator wording that
  keeps replay preview separate from persisted paper lifecycle actions
- 8D still deferred:
  expiration settlement mode; durable Orders visibility later landed in `9B`
  while broader provider/source parity remains future work
- 8D not included:
  naked short options, early partial fills, assignment/exercise automation, or
  live brokerage execution
- 8D manual smoke checklist:
  set `commission_per_contract` in Settings, open Recommendations in options
  mode, review research preview, run replay payoff preview, open paper
  option structure, manually close with per-leg exit premiums, verify
  gross/commission/net math, and confirm no live-trading language appears
- 8E status:
  `8E1` complete for the current Recommendations risk-summary foundation;
  `8E2` complete for the current Recommendations provider/source/as-of and
  data-quality warning scope; `8E3` complete for the current guided
  Recommendations workflow-clarity scope. `8E` is now closed for the current
  Recommendations options surface only.
- 8E acceptance target:
  operators can see strategy summary, legs, debit/credit, max profit/loss,
  breakevens, DTE/expiration, payoff context, warnings, provider/source
  labels, and Expected Move / Expected Range context without implying
  execution support
- 8E implemented now:
  Recommendations options research preview now includes a compact `Structure
  risk` surface that keeps research context, replay payoff preview, and the
  persisted paper lifecycle visually distinct while surfacing structure type,
  debit/credit, max profit/loss, breakevens, expiration / DTE, leg count,
  contract multiplier, Expected Range status/context, replay-preview status,
  paper lifecycle state, manual-close gross/net/commission outcome, and a
  compact caveat list that explicitly says Expected Range does not modify
  payoff math; the same surface now also shows workflow source, chain
  source/as-of, Expected Range provenance/as-of, safe `Source unavailable` /
  `As-of unavailable` copy, and provider-plan/payload warnings for missing
  chain, IV, Greeks, open interest, missing expiration/DTE, and SPX/NDX
  index-data caveats without implying execution approval; it now also adds a
  guided stepper for structure -> payoff preview -> paper save -> manual
  close -> paper-close result review, clearer paper-save wording that says no broker
  order is sent, explicit exit-premium instructions plus long/short hints,
  a stronger post-close result card, and lighter progressive disclosure so
  detailed provider/warning context stays available without overwhelming the
  operator; smoke-test polish now clarifies that the current chain preview is
  a lightweight reference snapshot, explains missing `last` / `volume`
  fields plus incomplete call-only or put-only chain sides safely, and labels
  the final guided step as the paper-close result rather than a generic saved
  result
- 8E not included:
  full chart-heavy payoff tooling, advanced Expected Move visualization in the
  first risk-UX slice, broader provider/source/as-of parity across additional
  options surfaces, or live-liquidity realism
- 8F status:
  complete for the current scoped paper-first options capability
- 8F acceptance target:
  supported options flows are coherent from research to replay to paper for the
  intended paper-only scope, tests are in place, deferred items remain
  explicit, and equity regressions stay green
- 8F implemented now:
  final closure audit confirms the current scoped options capability is
  complete: read-only research preview, read-only/non-persisted payoff
  preview, current paper-only open/manual-close lifecycle, commission-aware
  gross/net paper close results, and Recommendations risk/operator UX are all
  present and separately labeled without implying live routing, broker
  execution, expiration settlement, assignment/exercise automation, or other
  future options-parity work
- Phase 8 closure note:
  Phase 8 is complete for the current scoped paper-first options capability
  only. This does not imply advanced Expected Move visualization,
  provider/source/as-of parity across other options surfaces, expiration
  settlement, assignment/exercise automation, persisted options
  recommendations, options replay persistence, or live routing/execution.
- Phase 8 conservative sequence:
  `8C2.1` pure payoff math module and tests ->
  `8C2.2` vertical debit spread helpers/tests ->
  `8C2.3` iron condor helpers/tests ->
  `8C3.1` read-only replay preview contract ->
  `8C4.1` replay preview UI ->
  `8C5` replay tests/docs closure ->
  `8D1` schema/lifecycle design checkpoint ->
  `8D2` dedicated schema/migration foundation ->
  `8D3` repository/service contracts ->
  `8D4` open paper option structure ->
  `8D5` close paper option structure ->
  `8D6` contract commissions ->
  `8D7` operator UI ->
  `8D8` lifecycle tests/docs closure ->
  `8E` Recommendations options risk/operator UX closure ->
  `8F` closure review
- Phase 8 guardrails:
  options begin read-only, equity workflows must remain untouched unless
  explicitly tested, no live trading, no staged options orders until the
  correct phase, no schema until approved, no hidden execution semantics, no
  RecommendationService equity contamination, and no naked short support in
  early phases
- Phase 8 deferred items:
  persisted options recommendations, options replay persistence, staged options
  orders before runtime lifecycle slices, assignment/exercise automation,
  covered calls that depend on inventory modeling, mark-to-market /
  Greeks-driven valuation parity, advanced Expected Move visualization beyond
  the current contextual summary, and live routing remain outside the current
  implementation scope

### Phase 9 — Options operator parity and data-quality hardening
- Status:
  `9A` complete for planning; `9B` complete for the current durable paper
  options Orders/Positions visibility scope; `9C` complete for the current
  provider/source/as-of parity scope; `9D` complete for the current
  Recommendations Expected Range visualization scope
- Theme:
  durable operator visibility for current paper-first options plus consistent
  provider/data-quality framing, without adding live execution semantics
- 9A acceptance:
  scope, sequencing, safety boundaries, and explicit deferrals are documented
  for the post-Phase 8 options maturity pass
- 9B scope:
  options Orders/Positions dashboard parity
- 9B acceptance target:
  operators can see saved paper option positions and closed paper option
  trades outside Recommendations with clear paper-only labels, structure
  summaries, leg context, status, and gross/commission/net values where
  available, without contaminating current equity Orders behavior
- 9B implemented now:
  Orders now includes a dedicated `Paper Options Positions` section backed by
  a user-scoped `GET /user/options/paper-structures` contract and same-origin
  frontend proxy, showing open versus closed paper option lifecycle rows with
  status, timestamps, leg summaries, and gross/opening/closing/total/net
  paper results where available, while leaving existing equity Orders tables
  and actions unchanged
- 9C scope:
  provider/source/as-of parity across options surfaces
- 9C acceptance target:
  source/as-of context, reference-only chain caveats, incomplete call/put
  side warnings, and missing market-field handling are presented consistently
  across options research, payoff preview, paper lifecycle, and future durable
  operator surfaces
- 9C implemented now:
  Analysis options research now mirrors the existing Recommendations
  provider/source/as-of copy for Expected Range and chain preview fields where
  the setup payload already provides them; Orders durable paper-options rows now
  state that full provider/source metadata remains captured in research preview
  rather than persisted lifecycle rows; Provider Health adds options/index data
  caveats without implying execution enablement. No backend behavior, schema,
  lifecycle math, commission math, equity behavior, or UI actions changed.
- 9C closure:
  Complete for the current scoped options surfaces. Future provider-depth,
  deeper live probes, or new options-facing surfaces should reopen parity checks
  in their own phase rather than expanding this closure.
- 9D scope:
  Expected Move visualization
- 9D acceptance target:
  Expected Move remains research context only, gains clearer visualization
  only after durable operator visibility and provider/data-quality parity are
  stable, and still does not modify payoff math unless a later phase
  explicitly changes that contract
- 9D1 design checkpoint:
  complete; recommends a compact reusable horizontal range bar before any
  chart-heavy work, using existing `expected_range`, structure breakeven,
  max-profit/max-loss, expiration/DTE, and already-loaded replay payoff fields
  only. The visualization must show expected lower/upper bounds, optional
  current/reference price, breakeven markers, and muted unavailable/blocked
  states while saying Expected Range is research context only, does not change
  payoff math, and does not approve execution.
- 9D2 implemented now:
  a reusable frontend `ExpectedRangeVisualization` component renders a compact
  horizontal range bar from existing payload fields only and is integrated into
  the Recommendations `Structure risk` surface. It shows computed lower/upper
  bounds, reference-price context when derivable from the existing range,
  breakeven markers, expiration/DTE, max profit/loss labels, method/source/as-of
  and provenance text, blocked/unavailable states, and explicit research-only
  safety copy. Missing or invalid values render as `Unavailable` / `-` rather
  than `null`, `undefined`, `NaN`, or `Infinity`.
- 9D closure:
  complete for the current Recommendations Expected Range visualization scope.
  Closure audit tightened derived range-midpoint labeling so the component does
  not imply an actual current/reference price when the payload does not carry
  one, confirmed the component stays compact inside `Structure risk`, and kept
  Analysis integration optional/future.
- 9D not included:
  probability of profit, broker mark-to-market simulation, expiration
  settlement, assignment/exercise modeling, IV surface modeling, live
  execution decisions, provider probes, strategy scoring changes, or changes
  to options lifecycle, commission, equity, or recommendation-generation math
- Phase 9 implementation order:
  `9A` planning -> `9B` durable options Orders/Positions visibility
  complete -> `9C` provider/source/as-of parity complete for current scope ->
  `9D1` design checkpoint complete -> `9D2` reusable Expected Range
  visualization component plus first Recommendations integration complete ->
  `9D` closure audit complete for current Recommendations scope. Optional
  Analysis integration, richer replay/visual polish, and provider-depth work
  move to future phases only if explicitly reopened.
- Phase 9 closure:
  complete for the current options operator parity, provider/source/as-of, and
  Recommendations Expected Range visualization scope. No further explicit
  Phase 9 subphase is open unless future provider-depth or expanded options
  surfaces are intentionally reopened.
- Phase 9 not included:
  expiration settlement, assignment/exercise automation, persisted options
  recommendations, options replay persistence into equity replay flows, live
  routing/execution, broker integrations, or naked-short support

### Phase 10 - Deferred-work planning and safe options polish
- Status:
  planning started; `10A1` and `10B1` complete; broader `10A`, broader `10B`,
  and later subphases remain open
- Theme:
  organize remaining options/provider/crypto work into explicit risk bands and
  safe future slices before any higher-risk lifecycle, persistence, brokerage,
  probability, margin, or crypto implementation work begins
- Current safety posture:
  paper-first only; no live routing; no real brokerage execution; provider
  readiness does not equal execution enablement; Expected Range remains
  research context only; payoff preview does not equal a recommendation;
  options lifecycle remains paper-only; crypto remains future architecture /
  planning unless explicitly implemented later

#### Phase 10 deferred-work inventory and risk classification

Safe near-term:

- completed `10A1`: optional Analysis Expected Range visualization using the
  existing reusable component and existing setup payload fields only
- replay payoff visualization polish that remains read-only/non-persisted and
  does not change payoff math
- Orders dashboard polish for existing durable option positions/trades using
  already persisted fields only
- operator docs/training improvements and paper-only safety copy audits
- provider-health copy/readiness-only clarifications that do not add probes
- docs/design checkpoint for symbol discovery and watchlist management as
  recommendation-universe workflow polish, before any schema or runtime changes
- docs/design checkpoint for operator glossary and explainable metric tooltips
  before any shared component or registry work
- completed `10C1`: central glossary registry and reusable accessible
  metric-help component with narrow Settings, Expected Range, and Provider
  Health integrations
- completed `10C2`: Recommendations score/risk-label rollout for `Score`,
  `CONF` / confidence, `RR`, Expected Range, max profit/loss, breakevens,
  gross/net P&L, and options commission labels without changing scoring,
  lifecycle, payoff, commission, provider, schema, or execution behavior

Medium-risk:

- broader Orders dashboard parity if it needs new read-model joins or backend
  serialization, even without schema changes
- options replay/history integration design checkpoint because it touches
  future replay lineage and persistence semantics
- provider-depth/readiness probes if later implemented, because even safe
  probes can create paid-plan assumptions or imply execution readiness
- advanced Expected Move visualization beyond the current range bar if it
  introduces richer charting or interpretation language
- persisted options recommendations design, before implementation, because it
  must avoid `RecommendationService.generate()` drift and equity behavior
  changes
- symbol discovery and user-scoped watchlist implementation if it requires new
  symbol metadata tables, provider search calls, schedule/recommendation
  universe wiring, or import flows
- shared glossary registry and tooltip/popover implementation across Analysis,
  Recommendations, Replay, Orders, Settings, and Provider Health because it
  touches common UI primitives and app-wide wording consistency

High-risk:

- expiration settlement mode
- assignment/exercise automation
- partial fills for multi-leg option structures
- options replay persistence into replay runs
- persisted options recommendations implementation
- probability modeling / probability-of-profit
- margin modeling
- naked short support

Explicitly later / not now:

- live routing / broker execution / real brokerage execution
- crypto implementation or crypto paper execution
- naked short support, unless a later margin/risk program explicitly designs it
- assignment/exercise automation
- probability-of-profit as an execution or recommendation signal
- broad options order staging or brokerage order tickets
- treating discovered symbols, provider support labels, or options eligibility
  as execution approval
- describing `CONF`, `Score`, Expected Range, or replay/payoff outputs as
  probability of profit or execution approval without a separately designed
  and tested probability model

#### 10A - Options polish and operator workflow cleanup

- Type:
  frontend-only or docs-only first
- Complete when:
  optional Analysis Expected Range visualization, compact replay-payoff polish,
  or small operator-copy cleanup lands using existing payload fields only,
  with safe missing-value rendering and no backend behavior changes
- Explicitly not complete:
  replay persistence, options recommendations persistence, settlement,
  assignment/exercise, probability modeling, margin modeling, broker routing,
  or lifecycle math changes
- Must be tested:
  rendered source/as-of and unavailable states, research-only copy, no
  probability/execution/live-routing language, no `null` / `undefined` /
  `NaN` / `Infinity`
- Rollback/risk notes:
  hide or remove the frontend component/copy; no data migration or backend
  rollback should be required

First implementation slice:

- `10A1` optional Analysis Expected Range visualization. Reuse
  `ExpectedRangeVisualization` in Analysis options mode with existing
  `expected_range`, structure breakeven, expiration/DTE, source/as-of, and
  risk fields only. Keep it compact, read-only, and explicitly labeled as
  research context that does not change payoff math or approve execution.
- `10A1` status:
  complete for the current frontend-only slice. Analysis now reuses the
  existing Expected Range visualization component in options mode, including
  computed and unavailable expected-range states, without adding backend
  behavior, schema changes, provider probes, lifecycle actions, or payoff/math
  changes.

#### 10B - Orders dashboard parity for durable options rows

- Type:
  frontend-only first; backend read-model only if existing fields are
  insufficient and no schema change is needed
- Complete when:
  durable paper-options rows are easier to scan for open/closed state,
  expiration, DTE if derivable, legs, gross/opening/closing/total/net values,
  and source-metadata limitations without adding lifecycle actions
- `10B1` status:
  complete for the current frontend-only display/readability slice. Orders now
  labels durable paper-options rows as display-only paper lifecycle records,
  separates open paper positions from manually closed records, shows compact
  debit/credit, risk, commission, gross/net, status, and leg-detail tables
  from existing persisted lifecycle fields, and keeps provider/source/as-of
  limitations muted rather than error-like.
- Explicitly not complete:
  close/open actions from Orders, expiration settlement, partial fills, staged
  option orders, or brokerage routing
- Must be tested:
  open/closed row rendering, empty/loading/error states, safe unavailable
  values, durable metadata limitation copy, and equity Orders regression
- Rollback/risk notes:
  keep the dedicated options section removable without disturbing equity
  Orders tables

#### 10C1 - Operator glossary foundation

- Type:
  frontend-only shared foundation
- Complete when:
  a central glossary registry and reusable accessible metric-help component
  exist, the required initial terms are covered, and only low-risk surfaces are
  wired first
- Status:
  complete for the current first slice. `apps/web/lib/glossary.ts` now defines
  the initial terms, `MetricHelp` / `MetricLabel` provide compact
  click/tap/keyboard-accessible help, and Settings commission labels, Expected
  Range visualization labels, and Provider Health readiness context are wired
  without retrofitting the whole app.
- Explicitly not complete:
  broad Analysis, Recommendations tables, Replay, Orders, score columns,
  full glossary/reference page, probability modeling, provider probes,
  recommendation-generation changes, lifecycle behavior changes, payoff math
  changes, commission math changes, schema changes, live routing, or broker
  execution
- Must be tested:
  required registry terms, known/unknown `MetricHelp` rendering, commission
  guardrail copy, Expected Range research-only caveats, confidence/score
  non-probability wording, Provider readiness non-execution wording, and
  Settings integration
- Rollback/risk notes:
  remove the help icons/imports and leave the registry unused; no backend,
  data, or schema rollback should be required
- Note:
  this implements the glossary foundation slice requested as `10C1`; the
  separate options replay/history design checkpoint below remains open and is
  not closed by this work.

#### 10C - Options replay/history integration design checkpoint

- Type:
  docs-only first
- Complete when:
  a mode-native design exists for future options replay history and lineage,
  including whether options replay should have separate persistence rather than
  reusing equity `replay_runs`
- Explicitly not complete:
  options replay persistence, equity replay table changes, replay execution
  changes, or `RecommendationService.generate()` changes
- Must be tested later:
  no equity replay regressions, no persisted rows from read-only preview,
  explicit market-mode separation, and source/as-of continuity
- Rollback/risk notes:
  design-only checkpoint; do not implement until storage and UX boundaries are
  approved

#### 10D - Expiration settlement design checkpoint

- Type:
  docs-only first
- Complete when:
  the repo has a settlement-mode design covering required settlement price,
  expiration date checks, manual override/audit needs, long/short leg payoff at
  expiration, and explicit assignment/exercise exclusions
- Explicitly not complete:
  expiration settlement implementation, assignment/exercise automation, broker
  exercise actions, margin modeling, or naked short support
- Must be tested later:
  unsupported settlement rejection remains intact until implementation,
  settlement math fixtures, no double-close, user scoping, and equity
  lifecycle regression
- Rollback/risk notes:
  design-only checkpoint; implementation is high-risk and should require a
  separate approval pass

#### 10E - Provider-depth/readiness planning

- Type:
  docs-only first; later frontend/backend only if safe probes are explicitly
  approved
- Complete when:
  provider-depth gaps are listed without paid-plan assumptions and readiness
  copy remains clearly separated from execution enablement
- Explicitly not complete:
  new provider probes, paid-plan-specific claims, live routing, brokerage
  execution, or provider-based order approval
- Must be tested later:
  readiness-only copy, no execution implication, safe unavailable statuses,
  and no hidden provider/fallback mixing
- Rollback/risk notes:
  copy-only work is low risk; live probes are medium-risk and must be
  separately scoped

#### 10F - Crypto architecture planning only

- Type:
  docs-only
- Complete when:
  crypto mode requirements are documented separately from equities/options,
  including 24/7 sessions, spot/perpetual distinction, funding/basis context,
  provider assumptions, replay boundaries, and paper-only posture
- Explicitly not complete:
  crypto implementation, crypto provider wiring, crypto paper execution,
  crypto recommendations, or crypto UI actions
- Must be tested later:
  market-mode separation, no equities logic leakage, safe provider/fallback
  labels, and no execution implication
- Rollback/risk notes:
  planning-only; no runtime rollback

#### Future workflow polish - Symbol discovery and watchlist management

- Type:
  docs/design first; later frontend/user-workflow work only after explicit
  approval
- Purpose:
  replace comma-only symbol entry and ad hoc operator memory with a user-scoped
  recommendation-universe workflow. This is symbol discovery and research
  universe management only, not trade execution, routing, or broker support.
- Symbol discovery target:
  operators should eventually be able to search by ticker and company/security
  name; review ticker, name, asset type, exchange, provider/source support
  where available; distinguish equities, ETFs, indexes, options-eligible
  underlyings, and future crypto candidates where practical; and see ETF/index
  substitution guidance such as `SPX` / `NDX` versus `SPY` / `QQQ` without
  implying execution support.
- Watchlist target:
  replace raw comma-separated lists with searchable/sortable user-scoped
  watchlists that support add/delete of individual symbols, bulk add/import,
  duplicate handling, active/inactive status, optional tags/groups such as
  `Core`, `ETFs`, `Tech`, `Options Candidates`, and `Watch Only`, plus notes or
  source fields if useful.
- Recommendation-universe target:
  recommendation and scheduled-report workflows should eventually select from
  watchlists or groups rather than raw comma lists, while still allowing manual
  symbol entry when metadata is missing or provider lookup is unavailable.
- Guardrails:
  provider support labels must not imply live routing; missing metadata should
  not block manual symbol entry; options eligibility/provider coverage is
  research context, not execution approval; future crypto labels remain
  planning context until crypto is explicitly implemented; secrets and API keys
  stay out of docs and UI.
- Suggested implementation order:
  `design checkpoint` -> `read-only symbol search/source-label UX using
  existing provider capabilities only if already available` ->
  `user-scoped watchlist table UX` -> `bulk import/duplicate handling` ->
  `schedule/recommendation universe selection from groups` ->
  `provider-depth enrichment only if separately approved`.
- Explicitly not complete:
  schema changes, provider probes, provider search/fetch behavior, live
  routing, brokerage execution, recommendation generation changes, options
  execution approval, crypto implementation, or automatic strategy scoring
  changes.
- Must be tested later:
  search and fallback states, safe missing metadata rendering, duplicate
  handling, active/inactive filters, group/tag selection, manual-entry fallback,
  no provider/live-routing implication, and no change to
  `RecommendationService.generate()` behavior.
- Rollback/risk notes:
  design-only now; later implementation should be split so watchlist UI can be
  disabled without affecting existing scheduled reports or recommendation
  generation.

#### Future workflow polish - Operator glossary and explainable metric tooltips

- Type:
  docs/design first; later frontend/shared-component work only after explicit
  approval
- Purpose:
  make MacMarket's operator terms, abbreviations, formulas, and caveats
  understandable in context without changing recommendation generation,
  scoring, provider behavior, lifecycle math, commission math, or execution
  boundaries.
- Target surfaces:
  Analysis, Recommendations, Replay, Orders, Settings, Provider Health, and
  future symbol/watchlist workflows should eventually use the same definitions
  for labels, table headers, cards, and form fields.
- Tooltip/popover target:
  small info icons beside important labels should open concise
  hover/click/tap popovers with plain-English definitions, formulas where
  applicable, short examples when useful, and caveats such as `not execution
  approval`, `not probability of profit`, or `not live broker data`.
- Shared glossary target:
  implement a central glossary registry when this becomes code, so terms stay
  consistent across the app and can optionally power a future glossary or
  reference page.
- `10C1` status:
  complete for the first foundation slice. The shared registry and reusable
  metric-help component now exist, with first integrations limited to Settings
  commission labels, Expected Range visualization labels, and Provider Health
  readiness context.
- `10C2` status:
  complete for the Recommendations score/risk-label rollout. Queue score,
  confidence, and RR labels plus options risk labels for Expected Range, max
  profit/loss, breakevens, gross/net P&L, and options commissions now use the
  shared glossary help component where the labels are most visible.
- Initial term set:
  `RR` / risk-reward ratio, `CONF` / confidence, `Score`, Expected Range /
  Expected Move, `DTE`, `IV`, Open Interest, Breakeven, Max Profit, Max Loss,
  Gross P&L, Net P&L, equity commission per trade, options commission per
  contract, Provider readiness, Paper lifecycle, and Replay payoff preview.
- Design guidance:
  keep tooltips concise; send longer explanations to welcome/operator docs;
  avoid huge explanations in every table cell; support desktop hover plus
  keyboard, click, and touch behavior; keep visual weight low so the operator
  console stays dense and readable.
- Guardrails:
  `CONF` and `Score` must not be described as probability of profit unless a
  real probability model exists; Expected Range remains research context and
  does not change payoff math; Provider readiness does not imply live routing
  or execution; Paper lifecycle does not imply broker orders; commission copy
  must distinguish equity per-trade commissions from options per-contract
  commissions; secrets, API keys, and brokerage credentials stay out of docs
  and UI.
- Suggested implementation order:
  `glossary content/design checkpoint` -> `central glossary registry` ->
  `accessible InfoTooltip/MetricHelp component` -> `Settings and Provider
  Health low-risk labels` -> `Analysis and Recommendations score/risk labels`
  -> `Replay and Orders P&L/commission labels` -> `optional glossary page`.
  The Recommendations part of the score/risk-label step is complete in
  `10C2`; broader Analysis, Replay, and Orders rollout remains future work.
- Explicitly not complete:
  probability modeling, recommendation scoring changes, provider probes, live
  routing, broker execution, commission math changes, payoff math changes,
  lifecycle behavior changes, schema changes, or broad UI redesign.
- Must be tested later:
  consistent definitions from the registry, keyboard/touch accessibility,
  concise rendering in dense tables/cards, no probability-of-profit wording for
  `CONF` or `Score`, Expected Range research-only copy, provider-readiness
  non-execution copy, and commission distinction between equity and options.
- Rollback/risk notes:
  design-only now; later UI work should be removable by hiding the help icons
  without changing underlying workflow data or behavior.

#### 10G - Phase 10 closure

- Type:
  review/docs/test closure
- Complete when:
  Phase 10 completed slices are documented, deferred items remain explicit,
  validation is green for touched surfaces, and no safety boundary has moved
- Explicitly not complete:
  live brokerage execution, real routing, expiration settlement,
  assignment/exercise, naked shorts, probability/margin modeling, persisted
  options recommendations, options replay persistence, or crypto implementation

### Later execution / implementation tracks - not active
- Alpaca paper integration:
  `BROKER_PROVIDER=alpaca`, real paper order placement, fill polling, account
  reconciliation, and broker execution semantics remain future work. Keys may
  be configured and scaffold may exist, but `BROKER_PROVIDER=mock` remains the
  current production setting.
- Crypto implementation:
  crypto-native strategy design and crypto paper execution remain later work
  after `10F` planning and explicit operator strategy decisions.

## Still Open (no phase assigned)

- `/account` page does not render Clerk `<UserProfile>` for self-service MFA
  enrollment (Clerk paid feature; admin enrollment via Clerk dashboard works)
- `MacMarket-Strategy-Reports` scheduled task may be redundant with
  `MacMarket-StrategyScheduler` — operator should verify and delete if duplicate
- `display_id` collision possible if two recs created for same symbol+strategy
  within the same minute — needs suffix handling
- npm audit: vitest/vite/esbuild moderate-severity dev-server vulns
  (GHSA-67mh-4wv8-2f99) — dev-only, deferred until vitest 4 migration
- `save_alternative` backend action variant not yet implemented (UI button
  exists, disabled)
- `atm_straddle_mid` expected-range method contract-allowed but not yet emitted
  by preview logic
- Brand logo CDN — currently using `apps/web/public/brand/` static; consider
  Cloudflare R2 / dedicated logo CDN for production scale
- Email delivery: end-to-end Resend verification for scheduled report delivery
  to a real inbox (logo URL configurable via `BRAND_LOGO_URL`, From display
  name via `BRAND_FROM_NAME`)
- HACO workspace: deeper indicator controls and signal visibility
- Analysis / Recommendations chart UX follow-up:
  HACO parity, Playwright hover/legend coverage, and advanced indicator
  settings remain deferred beyond the coordinated lower-panel pass
- Sticky table headers + richer active-context toggles on Replay / Orders
  history tables (beyond current contained-scroll + lineage-first selection)
- Options/crypto live execution semantics — current options support is still
  paper-first only (research preview, read-only payoff preview, and
  paper-only lifecycle plus durable Orders visibility). Current provider and
  data-quality parity is closed under Phase 9; deeper provider-depth work,
  crypto implementation, and live execution remain deferred. Phase 10 now
  organizes these items into planning/polish/design slices before any runtime
  expansion.
- Symbol discovery and watchlist management — current symbol entry and
  scheduled-report watchlists remain too manual. A future workflow-polish item
  now covers searchable ticker/name discovery, user-scoped watchlists,
  sortable/filterable symbol tables, bulk import, duplicate handling,
  active/inactive symbols, optional groups/tags, provider/source support
  labels, ETF/index substitution guidance, and eventual recommendation-universe
  selection from watchlists without implying execution support.
- Operator glossary and explainable metric tooltips — many current surfaces
  expose abbreviations and metrics such as `RR`, `CONF`, `Score`, `DTE`,
  Expected Range, `IV`, open interest, breakevens, gross/net P&L, commissions,
  provider readiness, paper lifecycle, and replay payoff preview. A future
  workflow-polish item now covers a shared glossary registry plus accessible
  in-context help, while keeping confidence/score separate from probability of
  profit and preserving paper-only/non-execution guardrails. `10C1` has landed
  the shared foundation and first low-risk integrations; `10C2` has landed the
  Recommendations score/risk-label rollout. Broader Analysis, Replay, Orders,
  and glossary-page rollout remains open.

## Deployment State
- URL: https://macmarket.io
- Tunnel: Cloudflare Tunnel (cloudflared Windows service, auto-start)
- Backend: uvicorn on `127.0.0.1:9510`
- Frontend: Next.js on `0.0.0.0:9500`
- DB: SQLite at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db`
- Backup: daily 3 AM via `MacMarket-DB-Backup` scheduled task
- Scheduler: every 5 min via `MacMarket-StrategyScheduler` scheduled task
- Alpha users: 3 (admin + 2 approved)
- Alpaca paper API keys: configured, `BROKER_PROVIDER=mock` (execution phase
  not active)

## Test Counts (last verified 2026-04-30)
- pytest: 210
- vitest: 170
- Playwright: 31

## Core product pillars
1. **Strategy Workbench** (`/analysis`) — primary setup entry, links into
   Recommendations.
2. **Recommendations Workspace** (`/recommendations`) — ranked queue,
   promote → persisted lineage, full provenance.
3. **Replay Lab** (`/replay-runs`) — deterministic historical replay with
   step-by-step approved/rejected outcomes.
4. **Paper Orders** (`/orders`) — stage from recommendation lineage, fill
   simulation, position lifecycle, close + reopen.
5. **Scheduled Strategy Reports** (`/schedules`) — recurring ranked scans
   with email delivery and run history.
6. **Symbol Analyze** (`/analyze`) — per-symbol snapshot for ad-hoc lookup.

## Operator click path (tester quickstart)
1. `/dashboard` → "Start guided paper trade" → `/analysis?guided=1`.
2. Pick symbol + strategy → "Refresh analysis" → "Create recommendation".
3. `/recommendations?guided=1&recommendation=…` → "Make active" auto-advances.
4. `/replay-runs?guided=1&…` → "Run replay now" auto-advances if stageable.
5. `/orders?guided=1&…` → "Stage paper order now" → blotter with lineage.
6. Close position → gross/net P&L with fees; reopen within 5 min if needed.

## LLM role
**Today:** extract events, summarize catalysts, explain context. Engines
decide and size; LLMs never produce trade decisions.
**Later:** richer narrative explanation of replay outcomes and recommendation
provenance. Decision logic remains deterministic.

## Multi-asset expansion policy
Equities are first-class today. Options now support a scoped paper-first
research/replay-preview/manual-close lifecycle centered on
`/recommendations`, plus durable paper-options visibility on `/orders` from
Phase 9B. Current provider/source/as-of parity is closed under Phase 9;
deeper provider-depth work remains future. Phase 10 now organizes deferred
options polish, provider-depth planning, and crypto architecture planning;
crypto implementation remains future work. Cross-mode `expected_range`
semantics
remain spec-defined only until preview payloads, scoring, replay, and later
mode-native operator surfaces carry method-tagged fields per mode.

## Detailed change log
Pass-by-pass detail (every closeout, every test count delta, every fix) is
preserved in git history. Run `git log --oneline -- docs/roadmap-status.md`
for the chronological list, or `git log -p docs/roadmap-status.md` for full
diffs. Notable recent inflection points:

- 2026-04-29 — Phase 8 master blueprint expanded: `docs/options-architecture.md`
  was tightened into a master plan and new companion docs now define the
  replay preview design, paper lifecycle design, operator risk UX design, and
  Phase 8 test matrix. This stayed docs-only; no schema, migration, replay,
  order-lifecycle, or execution behavior changed.
- 2026-04-29 — Analysis / Recommendations chart UX pass: workflow charts now
  default to compact presets instead of crowded overlays, surface hover
  snapshot values for time / close / volume plus visible indicators only, and
  show a value-rich legend with quick hide toggles. This stayed frontend-only;
  scoring, replay, orders, schemas, and provider execution behavior were not
  changed.
- 2026-04-29 — Analysis / Recommendations chart UX pass 2: workflow charts now
  render coordinated lower panels for volume and RSI with synchronized
  inspection context across panels, while keeping MACD, ATR, HACO parity,
  advanced indicator settings, and Playwright interaction coverage deferred.
  This remained frontend-only; options stayed research-only and no
  recommendation, replay, order, or provider behavior changed.
- 2026-04-29 — Phase 8A planning started: `docs/options-architecture.md`
  added with safe follow-on slices for read-only option contracts, replay,
  paper lifecycle, and operator risk UX. This was a docs-only pass; no
  schema, migration, or application-code changes landed.
- 2026-04-29 — Phase 8B complete for the current non-persisted
  research-visibility scope: Recommendations now exposes a read-only options
  research preview sourced from the protected Analysis setup contract,
  Analysis suppresses persisted recommendation creation for non-equities, and
  options-mode execution CTAs remain intentionally unavailable. This stayed
  frontend-only; no schema, migration, replay, order-lifecycle, or execution
  behavior changed.
- 2026-04-29 — Phase 8C planning pass: `docs/options-architecture.md` now
  defines options replay as a read-only, non-persisted replay-preview mode for
  defined-risk structures first, with vertical debit spreads and iron condor as
  the initial targets. Existing equity replay remains isolated, while staging,
  options paper lifecycle, and live routing stay deferred to later slices.
- 2026-04-29 — Phase 8C2 complete: isolated pure options payoff math landed in
  `src/macmarket_trader/options/payoff.py` with focused backend tests covering
  long-option primitives, vertical debit spreads, iron condor, blocked naked
  shorts, and invalid input handling. This stayed schema-free, route-free,
  persistence-free, and UI-free; existing equity replay behavior was unchanged.
- 2026-04-29 — Phase 8C3 complete: a dedicated read-only options replay
  preview contract landed at `POST /user/options/replay-preview`, backed by the
  isolated payoff helper and focused backend tests for ready/blocked/
  unsupported responses plus non-persistence. This remained schema-free,
  non-persisted, UI-free, and separate from existing equity replay routes.
- 2026-04-29 — Phase 8C4 complete: Recommendations options research mode now
  exposes an operator-facing replay payoff preview panel that calls the
  read-only preview contract, renders compact expiration payoff summaries and
  blocked reasons safely, and keeps persisted replay/order/staging CTAs
  suppressed. This remained frontend-focused and non-persisted.
- 2026-04-29 — Phase 8C5 closure review complete for the current read-only,
  non-persisted replay-preview scope: roadmap/design docs now align on the
  shipped 8C boundary, Expected Move / Expected Range remains explicitly
  contextual research input rather than payoff math, and the operator copy now
  says that expected range does not change expiration payoff math or enable
  execution.
- 2026-04-29 — Phase 8D1 design checkpoint complete: the options paper
  lifecycle plan now compares extending current equity tables versus a
  separate options-specific persistence branch, recommends dedicated
  structure/leg persistence, defines draft open/close payload shapes, and
  keeps schema, migration, commission application, and operator UI work
  deferred to later 8D slices.
- 2026-04-29 — Phase 8D4 complete: a dedicated open-only paper options
  lifecycle path now exists at `POST /user/options/paper-structures/open`,
  backed by the options repository contracts and validation helpers. Supported
  defined-risk structures create options-specific order and position headers
  plus legs without touching equity orders, replay runs, staged orders, or
  live routing. Close behavior, commission application, and frontend operator
  UI remain deferred to later 8D slices.
- 2026-04-29 — Phase 8D5 complete for the current manual-close scope: open
  paper option positions can now close through
  `POST /user/options/paper-structures/{position_id}/close`, which validates
  full-leg manual close input, blocks double close and cross-user access,
  persists options-specific trade headers plus legs, and computes gross P&L
  without applying commissions yet. Expiration settlement, commission
  application, and frontend operator UI remain deferred.
- 2026-04-29 — Phase 8D6 complete for the current manual-close scope:
  `commission_per_contract` now applies per contract per leg on both the open
  and manual-close events for the dedicated options paper lifecycle branch.
  Open responses now expose paper opening commissions, manual-close trade rows
  now persist `total_commissions` and `net_pnl`, trade legs now persist
  commission and net values, and existing equity `commission_per_trade`
  behavior remains untouched. Expiration settlement and frontend operator UI
  remain deferred.
- 2026-04-29 — Phase 8D7 complete for the current paper-only manual-close
  scope: Recommendations options research preview now includes a separate
  paper option lifecycle panel with persisted paper open/manual-close actions,
  explicit `commission_per_contract` guardrails and example math, same-origin
  open/close proxies, and in-memory close inputs/results for the newly opened
  position only. Replay payoff preview remains read-only/non-persisted, equity
  workflows remain untouched, and broader Orders parity plus expiration
  settlement remain deferred.
- 2026-04-29 — Phase 8D8 closure/audit complete for the current paper-only
  manual-close scope: roadmap/design/test docs now align on `8D1` through
  `8D8`, the Recommendations options surfaces now keep replay preview wording
  distinct from the persisted paper lifecycle wording, proxy tests now cover
  success plus failure pass-through behavior, and the manual smoke checklist
  is documented. Expiration settlement, broader Orders parity, and `8E` risk
  UX remain deferred.
- 2026-04-29 — Phase 8E1 complete for the current Recommendations options
  research surface: a compact `Structure risk` layer now summarizes structure
  type, debit/credit, max profit/loss, breakevens, expiration / DTE, Expected
  Range status/context, replay-preview status, paper lifecycle state, and
  manual-close gross/commission/net outcome while keeping research preview,
  replay payoff preview, and persisted paper lifecycle visually distinct.
- 2026-04-29 — Phase 8E2 complete for the current Recommendations options
  provider/source/as-of and data-quality warning scope: the same `Structure
  risk` layer now surfaces workflow source, chain source/as-of, Expected
  Range provenance/as-of, safe `Source unavailable` / `As-of unavailable`
  rendering, and provider-plan/payload warnings for missing chain, IV,
  Greeks, open interest, missing expiration/DTE, and SPX/NDX index-data
  caveats without changing backend behavior or widening the page into a new
  dashboard.
- 2026-04-29 — Phase 8E3 complete for the current guided Recommendations
  options workflow UX: the same surface now adds a five-step operator guide,
  clearer paper-save wording, more explicit manual-close exit-premium help,
  a stronger post-close result state, and lighter progressive disclosure for
  detailed caveats without changing backend behavior or widening the feature
  scope.
- 2026-04-29 — Phase 8E closure review complete for the current
  Recommendations options surface: replay preview, read-only research context,
  and persisted paper-only lifecycle wording are now aligned; the replay
  preview no longer echoes execution-enabled copy; the current operator risk,
  provider/source, Expected Range, guided workflow, and manual-close clarity
  gates are documented as satisfied without implying full Phase 8 closure.
- 2026-04-29 — Phase 8F final closure complete for the current scoped
  paper-first options capability: frontend (`npm test`, `npx tsc --noEmit`)
  plus backend (`tests/test_options_paper_open_lifecycle.py`,
  `tests/test_options_paper_close_lifecycle.py`,
  `tests/test_options_replay_preview.py`) validation passed; docs now mark
  `8A` through `8F` complete for the scoped paper-first capability while
  keeping expiration settlement, assignment/exercise automation, persisted
  options recommendations, broader Orders parity, advanced Expected Move
  visualization, and live routing/execution explicitly deferred.
- 2026-04-29 — Phase 9 planning update complete: roadmap now defines `9A`
  through `9D` as the next options maturity phase focused on durable operator
  visibility and provider/data-quality parity, renumbers later Alpaca/crypto
  phases to preserve ordering, and keeps settlement, assignment, persisted
  options recommendations, live routing, and broker integration explicitly
  deferred.
- 2026-04-29 — Phase 9B complete for the current durable paper-options
  Orders/Positions visibility scope: a user-scoped paper-options list
  contract now surfaces saved open and closed paper option lifecycle records
  through Orders, using the dedicated options persistence path without
  changing equity order/replay behavior, live-routing boundaries, or options
  lifecycle math. Frontend and targeted backend validation passed.
- 2026-04-29 - Phase 9C1 complete for the current provider/source/as-of parity
  micro-pass: Analysis options Expected Range and chain preview copy now uses
  existing source/as-of/provenance fields and safe fallback text, Orders
  durable paper-options rows document that full provider/source metadata remains
  research-preview context, and Provider Health carries options/index data
  caveats as readiness context only. Remaining 9C parity and 9D visualization
  stay planned.
- 2026-04-29 - Phase 9C complete for the current provider/source/as-of parity
  closure scope after audit: Analysis, Recommendations, Orders durable
  paper-options rows, Provider Health, and operator guidance now present source,
  as-of/provenance, provider-plan limitations, and durable metadata limitations
  consistently where existing payload fields allow. No backend, schema,
  lifecycle, commission, equity, provider-fetch, or execution behavior changed.
  Full Phase 9D implementation remained planned.
- 2026-04-29 - Phase 9D1 design checkpoint complete for advanced Expected
  Move / Expected Range visualization: docs now recommend a compact reusable
  horizontal range bar using existing expected-range, breakeven, expiration/DTE,
  max-profit/max-loss, and already-loaded replay payoff fields only. The
  implementation remains deferred, and probability of profit, broker
  mark-to-market, settlement, assignment/exercise, provider probes, scoring
  changes, live routing, and math changes stay out of scope.
- 2026-04-30 - Phase 9D2 complete for the first reusable Expected Range
  visualization slice: a frontend-only component now renders a compact
  horizontal range bar inside Recommendations `Structure risk` using existing
  expected-range, breakeven, expiration/DTE, risk, source/as-of, and provenance
  fields only. Focused frontend tests cover computed, blocked, missing, safe
  rendering, and safety-copy states. No backend, schema, provider-fetch,
  lifecycle, commission, equity, recommendation-generation, payoff-math, or
  execution behavior changed.
- 2026-04-30 - Phase 9D closure complete for the current Recommendations
  Expected Range visualization scope: audit/polish confirmed lower/upper
  bounds, breakeven markers, blocked/missing states, safe invalid-number
  rendering, compact placement, and research-only safety copy. A tiny label
  polish now distinguishes a derived range midpoint from an actual
  current/reference price. Frontend validation passed at 160 vitest tests plus
  clean TypeScript; no backend, schema, provider, lifecycle, commission,
  equity, payoff, recommendation-generation, routing, settlement, assignment,
  exercise, naked-short, or probability behavior changed.
- 2026-04-30 - Phase 9 status/closure audit complete: current Phase 9 scope is
  closed across durable options Orders visibility, provider/source/as-of parity
  on the practical options surfaces, and the Recommendations Expected Range
  visualization. Remaining items are explicitly deferred future/provider-depth
  work rather than blockers for Phase 9 closure.
- 2026-04-30 - Phase 10 planning move complete: roadmap now treats Phase 10 as
  a documentation-first sequencing and safe-polish track for deferred options,
  provider-depth, replay/history, settlement-design, and crypto-architecture
  work. The initially recommended first implementation slice was `10A1`, an optional
  Analysis Expected Range visualization using existing payload fields and the
  existing reusable component only. Live routing, real brokerage execution,
  expiration settlement implementation, assignment/exercise automation, naked
  shorts, persisted options recommendations, options replay persistence,
  probability/margin modeling, and crypto implementation remain explicitly
  later/not-now.
- 2026-04-30 - Phase 10A1 complete: Analysis options setup now reuses the
  existing Expected Range visualization component with current setup payload
  fields only. The slice stayed frontend-only and keeps Expected Range as
  research context that does not change payoff math or approve execution.
  Backend behavior, schema, provider probes, lifecycle math, commission math,
  equity behavior, recommendation generation, live routing, settlement,
  assignment/exercise, naked-short support, probability modeling, and crypto
  implementation remain unchanged.
- 2026-04-30 - Phase 10B1 complete: Orders durable paper-options visibility
  now has a frontend-only display/readability polish pass. The section clearly
  describes display-only durable paper lifecycle records, no broker orders
  sent, manual close remaining in Recommendations, provider/source/as-of
  metadata limits, open versus manually closed paper states, compact
  debit/credit/risk/commission/gross/net summaries, and expandable leg detail
  tables using existing persisted options lifecycle fields only. No backend,
  schema, provider, lifecycle, commission, equity, replay, recommendation,
  routing, settlement, assignment/exercise, naked-short, probability, or crypto
  behavior changed.
- 2026-04-30 - Future symbol discovery and watchlist management roadmap item
  added: a docs-only planning note now tracks searchable ticker/name discovery,
  user-scoped searchable/sortable watchlists, bulk import, duplicate handling,
  active/inactive symbols, optional tags/groups, provider/source support
  labels, SPX/NDX versus SPY/QQQ substitution guidance, and eventual
  recommendation-universe selection from watchlists. This remains
  recommendation-universe management only, with no application code, schema,
  provider probes, live routing, brokerage execution, or recommendation
  generation behavior changed.
- 2026-04-30 - Future operator glossary and explainable metric tooltips
  roadmap item added: a docs-only planning note now tracks concise
  hover/click/tap metric help, formulas and examples where useful, a shared
  glossary registry, optional future glossary/reference page, accessibility
  expectations, and initial terms including `RR`, `CONF`, `Score`, Expected
  Range, `DTE`, `IV`, open interest, breakevens, max profit/loss, gross/net
  P&L, equity and options commissions, provider readiness, paper lifecycle,
  and replay payoff preview. This does not change application code, schema,
  provider probes, live routing, brokerage execution, recommendation
  generation, probability modeling, payoff math, lifecycle math, or commission
  math.
- 2026-04-30 - Phase 10C1 complete for the explainable metric UX foundation:
  frontend now has a central glossary registry, reusable `MetricHelp` /
  `MetricLabel` component, focused tests for required terms and safety copy,
  and narrow first integrations in Settings commission labels, Expected Range
  visualization labels, and Provider Health readiness context. Broader
  Analysis/Recommendations/Replay/Orders rollout remains future work, and no
  backend, schema, provider, lifecycle, commission, equity, recommendation,
  routing, settlement, assignment/exercise, naked-short, probability, symbol
  discovery, watchlist, or crypto behavior changed.
- 2026-04-30 - Phase 10C2 complete for Recommendations explainable metric
  labels: compact `MetricLabel` help now appears on queue `Score`, `RR`, and
  `CONF` labels plus the options risk/paper-lifecycle labels for Expected
  Range, max profit/loss, breakevens, gross/net P&L, and options
  commissions. Frontend tests cover the rollout and safety wording. No
  backend, schema, provider, recommendation scoring, equity, lifecycle,
  payoff, commission, routing, settlement, assignment/exercise,
  symbol-discovery, watchlist, probability, or crypto behavior changed.
- 2026-04-29 — Phase 7A/7B complete for current equity/paper scope:
  commission-aware gross/net realized paper P&L, per-user commission
  settings, replay/order/open-position fee previews, orders/settings UI
  updates, and equity close-math fee application. `commission_per_contract`
  storage landed, but options parity remains open.
- 2026-04-29 — Phase 7C complete for current paper/provider-readiness scope:
  Admin / Provider Health expanded into an operator-readiness console with
  explicit Alpaca paper readiness plus FRED and news readiness entries. This
  remains a paper/provider trust gate only; no live brokerage execution was
  enabled.
- 2026-04-29 — Pass 4: `display_id`, per-user risk dollars, Settings page,
  invite-email welcome CTA, schedules timezone display, MFA runbook, brand
  header on pre-auth, dashboard 401 hardening (`pending-approval` redirect).
- 2026-04-28 — Phase 6 close-out: cancel staged order, reopen closed position
  (5-min undo), email logo base64 inlining, scheduler runner script,
  in-browser welcome guide, sticky Active Trade banner, readable lineage
  breadcrumb, conditional CTA pulse states, replay step bar labels.
- 2026-04-16 — Polygon hardening: `SymbolNotFoundError`, `DataNotEntitledError`,
  options chain preview, index symbol normalization. Admin user-management
  hardening pass 1 + 2 (suspend, unsuspend, force re-login, hard delete,
  invite revoke/resend, role toggle).
- 2026-04-15 — Phase 6 close-trade lifecycle backend; Polygon live market
  data; transactional email polish; operational readiness audit; second-
  operator readiness checklist in runbook.
- 2026-04-12 — Phase 3 (paid beta scaffolding) + Phase 4 (vendor integration)
  closeouts.
- 2026-04-04 — Phase 1 closeout passes (provider truth, identity
  reconciliation, market-mode foundation, Windows deployment validation).
- 2026-04-03 — Initial Phase 1 hardening passes.
