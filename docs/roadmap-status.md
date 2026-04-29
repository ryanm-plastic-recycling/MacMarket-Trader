# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-04-29

## Positioning
MacMarket-Trader is positioned as an invite-only, operator-grade trading
intelligence console — not "another charting page." The defensible edge is
strategy-aware analysis, event + regime context, explicit trade levels,
replay before paper execution, recurring ranked trade reports, and
explainable AI layered on top of deterministic logic. **It is paper-only.**

## Current Status
Phases 0–6 and Pass 4 complete. Three alpha users (admin + 2 approved).
Deployed at https://macmarket.io via Cloudflare Tunnel.
Tests: pytest 210, vitest 123, Playwright 31. tsc clean.
Phase 7 is complete for the current equity/paper-readiness foundation.
Phase 8C is complete for the current read-only, non-persisted options replay
preview scope.
Phase 8D2 schema foundation is complete; repository/service and lifecycle
implementation remain deferred.
Remaining fee-depth, options-fee, and provider-depth items are intentionally
deferred to later phases and do not block Phase 8 planning.

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
- 31 Playwright e2e gates, 99 vitest helper tests, 210 backend pytest gates

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
  replay-preview scope, `8D1` and `8D2` complete for design plus dedicated
  schema foundation, and `8D3+` / `8E` / `8F` remain planned. Dedicated
  options persistence tables now exist, but no repository/service wiring,
  lifecycle behavior, UI, or execution-enablement changes have landed for
  options.
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
  `8D1` design checkpoint complete and `8D2` schema/migration foundation
  complete; `8D3+` remain deferred
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
  breakevens, `execution_enabled=false` defaults on option paper orders, and
  focused schema/migration tests; current equity write tables and routes remain
  untouched
- 8D still deferred:
  repository/service contracts, open paper option structure behavior, close
  paper option structure behavior, `commission_per_contract` application, and
  frontend operator UI
- 8D not included:
  naked short options, early partial fills, assignment/exercise automation, or
  live brokerage execution
- 8E status:
  planning complete; implementation not started
- 8E acceptance target:
  operators can see strategy summary, legs, debit/credit, max profit/loss,
  breakevens, DTE/expiration, payoff context, warnings, provider/source
  labels, and Expected Move / Expected Range context without implying
  execution support
- 8E not included:
  full chart-heavy payoff tooling, advanced Expected Move visualization in the
  first risk-UX slice, or live-liquidity realism
- 8F status:
  planned only; closure criteria defined
- 8F acceptance target:
  supported options flows are coherent from research to replay to paper for the
  intended paper-only scope, tests are in place, deferred items remain
  explicit, and equity regressions stay green
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
  `8D6` `commission_per_contract` application ->
  `8D7` operator UI ->
  `8D8` lifecycle tests/docs closure ->
  `8E1` operator risk UX improvements ->
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

### Phase 9 — Alpaca paper integration
- Wire `BROKER_PROVIDER=alpaca` for real paper fills
- Order placement via `https://paper-api.alpaca.markets`
- Poll for fills, reconcile against local `paper_positions`
- Keys configured in `.env`: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`,
  `ALPACA_PAPER_BASE_URL`. Scaffold exists at
  `src/macmarket_trader/execution/AlpacaBrokerProvider`. Not yet active.

### Phase 10 — Crypto
- Crypto-native strategy design (separate from equity momentum patterns —
  mean reversion, funding rate, BTC dominance regime)
- Crypto paper execution via Alpaca
- Prerequisite: operator must specify desired strategies before implementation

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
- Options/crypto live execution semantics — currently blocked at research
  preview only on `/recommendations` (full execution parity tracked under
  Phase 8 / Phase 10)

## Deployment State
- URL: https://macmarket.io
- Tunnel: Cloudflare Tunnel (cloudflared Windows service, auto-start)
- Backend: uvicorn on `127.0.0.1:9510`
- Frontend: Next.js on `0.0.0.0:9500`
- DB: SQLite at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db`
- Backup: daily 3 AM via `MacMarket-DB-Backup` scheduled task
- Scheduler: every 5 min via `MacMarket-StrategyScheduler` scheduled task
- Alpha users: 3 (admin + 2 approved)
- Alpaca paper API keys: configured, `BROKER_PROVIDER=mock` (Phase 9 activates)

## Test Counts (last verified 2026-04-29)
- pytest: 210
- vitest: 123
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
Equities are first-class today. Options and crypto are research-preview only
on `/recommendations`. Live replay and paper orders for options unlock with
Phase 8; crypto unlocks with Phase 10. Cross-mode `expected_range` semantics
remain spec-defined only until preview payloads, scoring, and replay carry
method-tagged fields per mode.

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
