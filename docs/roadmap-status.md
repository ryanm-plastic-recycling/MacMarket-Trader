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
Tests: pytest 210, vitest 99, Playwright 31. tsc clean.
Active passes: Phase 7 started early — commission-aware paper P&L credibility.

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

## Upcoming Phases

### Phase 7 — Brokerage fees + commission modeling
- Started early in repo:
  `gross_pnl` / `net_pnl` split in `paper_trades`
- Started early in repo:
  per-trade equity commission (default `$0`) applied to paper close math
- Started early in repo:
  commission settings exposed in user Settings page
- Started early in repo:
  backend fields on `paper_trades` and per-user `commission_per_trade` /
  `commission_per_contract` on `app_users` with env fallback defaults
- Still open:
  per-contract options commission parity in options replay / paper lifecycle
- Still open:
  broader fee modeling beyond current equity paper close flows

### Phase 8 — Options execution (research → paper parity)
- 8A: Options replay — historical P&L tracking for multi-leg structures using
  Polygon options data
- 8B: Options paper orders — stage, fill, position tracking, expiry awareness,
  auto-close on expiry
- 8C: Greeks + IV display on recommendations (delta, theta, vega, gamma,
  IV rank/percentile)
- 8D: IV rank as Iron Condor strategy gate input
- Prerequisite: Phase 7 commission model (options fees materially affect P&L)

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
- vitest: 99
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
