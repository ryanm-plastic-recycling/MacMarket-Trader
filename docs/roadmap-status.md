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
Tests: pytest 210, vitest 106, Playwright 31. tsc clean.
Phase 7 is complete for the current equity/paper-readiness foundation.
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
  architecture planning started; no schema, migration, or application-code
  changes landed in this pass
- Detailed plan:
  see [options-architecture.md](options-architecture.md)
- 8A:
  architecture and contract planning only
- 8B:
  safest first implementation slice after approval — read-only options
  research contracts in Analysis / Recommendations using existing chain
  preview and expected-range scaffolding where practical
- 8C:
  options replay for defined-risk structures, kept mode-separate from current
  equity replay
- 8D:
  options paper order / fill / position / trade lifecycle with
  `commission_per_contract` application
- 8E:
  operator risk UX for legs, credits/debits, max profit/loss, breakevens, and
  expiration caveats
- 8F:
  closure criteria for supported options paper-parity flows
- Phase 8 guardrails:
  paper-only, no live routing, no naked short options in early
  implementation, no assignment/exercise automation, and no margin assumptions
  unless explicitly modeled later

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
- vitest: 106
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
