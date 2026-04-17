# MacMarket-Trader — Claude Code Session Context

This file is read automatically by Claude Code at session start to orient each conversation.
Do not condense or rewrite the architecture or setup sections. Only update the **Current Phase Status** and **Open Items** sections as work progresses.

---

## What this repo is

MacMarket-Trader is a **research-first, event-driven trading intelligence console** for U.S. large-cap equities and liquid sector ETFs.

Design principle: **LLMs explain and extract. Rules and models decide and size.**

The system ingests market/macro/company events → normalizes them → classifies regime → produces deterministic, auditable trade recommendations → routes to paper execution → measures outcome, attribution, and replay/live parity over time.

Full architecture charter: `README.md` (canonical — do not summarize or replace it).

---

## Stack

| Layer | Tech | Location |
|---|---|---|
| Backend API | Python + FastAPI + SQLite (SQLAlchemy/Alembic) | `src/macmarket_trader/` |
| Frontend | Next.js (TypeScript, App Router) | `apps/web/` |
| Auth | Clerk (identity) + local `app_users` DB (role/approval truth) | Both layers |
| DB migrations | Alembic | `alembic/` |
| Backend tests | pytest | `tests/` |
| Frontend tests | Vitest + Playwright e2e | `apps/web/` |

**Dev path:** `C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader`
**Deployed path:** `C:\Dashboard\MacMarket-Trader`
**Deploy bridge:** `.\deploy-macmarket-trader.bat` (copies dev → deployed + starts servers)

---

## Key paths

```
src/macmarket_trader/
  api/routes/admin.py          — protected user + admin route handlers
  api/routes/analysis.py       — strategy workbench backend
  replay/engine.py             — deterministic replay runner
  recommendation/service.py    — recommendation generation
  indicators/                  — HACO/HACOLT indicator math
apps/web/
  app/(console)/               — operator console pages
    analysis/page.tsx          — Strategy Workbench
    recommendations/page.tsx   — Recommendations workspace
    replay-runs/page.tsx       — Replay workspace
    orders/page.tsx            — Paper Orders workspace
  components/
    workflow-banner.tsx        — guided flow context chip bar
    guided-step-rail.tsx       — step 1–4 rail navigation
  lib/
    guided-workflow.ts         — guided state parse/build helpers
    recommendations.ts         — queue/provenance helpers
tests/                         — backend pytest suite
apps/web/tests/e2e/            — Playwright e2e suite
```

---

## Dev setup

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m uvicorn macmarket_trader.api.main:app --reload --port 9510

# Frontend
cd apps/web
npm install
npm run dev        # port 9500 (or 3000 in dev)
```

**Minimum `.env` for local dev (no real providers):**
```
ENVIRONMENT=local
AUTH_PROVIDER=mock
EMAIL_PROVIDER=console
WORKFLOW_DEMO_FALLBACK=true
POLYGON_ENABLED=false
MARKET_DATA_PROVIDER=fallback
MARKET_DATA_ENABLED=false
```

**Minimum `apps/web/.env.local`:**
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
BACKEND_API_ORIGIN=http://127.0.0.1:9510
```

---

## Test and build commands

```bash
# Backend tests
pytest -q

# Frontend type check
cd apps/web && npx tsc --noEmit

# Frontend unit tests
cd apps/web && npm test

# Frontend build (full type + bundle check)
cd apps/web && npm run build

# Seed demo data
python -m macmarket_trader.cli seed-demo-data

# Run due scheduled reports
python -m macmarket_trader.cli run-due-strategy-schedules
```

---

## Auth and approval source-of-truth rules

- **Clerk** = identity boundary only (session verification).
- **Local `app_users` DB** = source of truth for `approval_status`, `app_role`, approval history.
- First login creates a local pending user (`approval_status=pending`, `app_role=user`).
- Subsequent logins only sync identity fields; they never overwrite local role/approval state.
- `/api/user/me` must always reflect local DB role.

---

## Guided workflow

Primary operator path: **Analysis → Recommendations → Replay → Paper Orders**

Context threads through URL query params: `guided=1`, `symbol`, `strategy`, `market_mode`, `source`, `recommendation` (UID), `replay_run` (ID), `order` (ID).

`WorkflowBanner` (`components/workflow-banner.tsx`) renders the active lineage as chips.
`GuidedStepRail` renders the 1–4 step rail.
`parseGuidedFlowState` / `buildGuidedQuery` in `lib/guided-workflow.ts` are the canonical helpers.

---

## Important implementation constraints

- `user_is_approved=True` must be passed to `recommendation_service.generate()` during replay so quality-gate overrides apply and `has_stageable_candidate` is computed correctly.
- Promote endpoint (`/user/recommendations/queue/promote`) now accepts `action` field (`make_active` / `save_alternative`) — stored in `ranking_provenance` and returned in response.
- Sticky `thead th` pattern: inline styles `position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)"`.
- `op-error` block style: `border: 1px dashed #7c4040; background: #2a1717`.

---

## Current Phase Status

**CURRENT STATE: Phases 0–6 complete + post-launch polish. 166 backend tests. 8 Playwright e2e. tsc clean.**

### Completed (DataNotEntitledError / 402 handling — 2026-04-16)

**`DataNotEntitledError` (`market_data.py`, `admin.py`, `analysis/page.tsx`)**
- `DataNotEntitledError(Exception)` added to `market_data.py` — distinct from `ProviderUnavailableError`.
- `_fetch_url`: HTTP 403 → `DataNotEntitledError("Not entitled to this data. Upgrade plan at https://polygon.io/pricing")`.
- `MarketDataService.historical_bars` / `latest_snapshot`: re-raise alongside `SymbolNotFoundError` (no fallback).
- `_workflow_bars` in `admin.py`: catches `DataNotEntitledError` → HTTP 402 `{ "error": "data_not_entitled", "message": "Your data plan does not include {symbol}. Index bar data (SPX, NDX, VIX) requires a plan upgrade." }`.
- Frontend: 402 response sets `workbenchState = "data_not_entitled"` — shows `StatusBadge tone="warn"` notice with ETF substitution hints (SPY/QQQ). Does not show provider-unavailable banner. `WorkbenchState` union updated.
- 3 new tests → 166 total: 403→`DataNotEntitledError` via module-level `urlopen` patch, service-level propagation, full route 402 response test.

### Completed (Polygon options chain preview — 2026-04-16)

**Fix 3 — Options chain preview (`market_data.py`, `admin.py`, `analysis/page.tsx`)**
- `PolygonMarketDataProvider.fetch_options_chain_preview(symbol, limit=50)` — calls `/v3/reference/options/contracts` (Polygon Options Basic plan). Returns nearest-expiry calls/puts as `{ strike, expiry, last_price: null, volume: null }`. Gracefully handles 404/empty/unavailable.
- `MarketDataService.options_chain_preview(symbol, limit)` — delegates to Polygon; returns `None` for non-Polygon providers.
- `analysis_setup` adds `options_chain_preview` to payload when `market_mode == OPTIONS`.
- Frontend: "Options chain preview" `Card` on analysis page for options mode. Shows calls/puts tables or reason message. `SetupPayload` type updated.
- `INDEX_SYMBOLS` updated to include "OEX".
- 5 new tests → 163 total.

### Completed (Polygon symbol handling — 2026-04-16)

**Fix 1 — `SymbolNotFoundError` (`market_data.py`, `admin.py`)**
- New `SymbolNotFoundError(Exception)` class in `market_data.py` — distinct from `ProviderUnavailableError`.
- `_fetch_url`: HTTP 404 → `SymbolNotFoundError`. Other HTTP errors → `ProviderUnavailableError` (unchanged).
- `get_historical_bars`: raises `SymbolNotFoundError` when no results returned after pagination.
- `get_latest_snapshot`: raises `SymbolNotFoundError` when `ticker` is None in Polygon response.
- `MarketDataService.historical_bars` / `latest_snapshot`: re-raise `SymbolNotFoundError` (not caught → no fallback).
- `_workflow_bars` catches `SymbolNotFoundError` → HTTP 400 `{ "error": "symbol_not_found", "message": "..." }`.

**Fix 2 — Index symbol normalization (`market_data.py`)**
- `INDEX_SYMBOLS = {"SPX", "NDX", "RUT", "VIX", "DJI", "COMP"}` constant.
- `normalize_polygon_ticker(symbol)` helper — maps known indices to `I:{symbol}`, passes others unchanged.
- Applied in `get_historical_bars` and `get_latest_snapshot` before building Polygon URL paths.

**7 new tests → 158 total**: normalize_polygon_ticker, index ticker URL paths, SymbolNotFoundError propagation, full 400 route test.

### Completed (admin hardening pass 2 — 2026-04-16)

**Fix 1 — Sign-up error boundary**
- `apps/web/app/sign-up/[[...sign-up]]/error.tsx` — route-level error boundary with "Try again" + "Go to sign in" links
- `apps/web/app/global-error.tsx` — root-level global error boundary with full `<html>` wrapper

**Fix 2 — Unsuspend / re-approve (`admin.py`, `[userId]/unsuspend/route.ts`)**
- `POST /admin/users/{user_id}/unsuspend` — sets status → approved; 409 if self; 404 if not found
- `approve_user` already handles rejected → approved; both flows covered

**Fix 3 — Hard delete user (`admin.py`, `repositories.py`, `[userId]/route.ts`)**
- `DELETE /admin/users/{user_id}` — 409 if self, 404 if not found; removes local DB record permanently

**Fix 4 — Force re-login via Clerk session invalidation (`admin.py`, `[userId]/force-password-reset/route.ts`)**
- `POST /admin/users/{user_id}/force-password-reset` — calls Clerk `DELETE /v1/users/{clerk_id}/sessions`; guards against invalid IDs, missing key, network failure (502)

**Fix 5 — Status-aware action matrix (`admin-users-panel.tsx`)**
- `approved`: Suspend + role toggle in row; Force re-login + Delete in expanded row
- `suspended`: Unsuspend in row; Force re-login + Delete in expanded row
- `rejected`: Approve in row; Delete in expanded row
- `pending`: Approve + Reject in row; Delete in expanded row
- Own row: all mutating actions hidden with tooltip

**New proxy routes**: `[userId]/unsuspend/route.ts`

**Backend tests (5 new → 151 total)**
- `test_re_approve_suspended_user`, `test_re_approve_rejected_user`, `test_delete_user_scoped_to_admin`, `test_delete_user_cannot_target_self`, `test_force_relogin_calls_clerk_session_invalidation`

### Completed (transactional email polish — 2026-04-15)

**Approval notification email**
- `render_approval_html(to_email, display_name, console_url)` in `email_templates.py` — dark-themed, inline CSS, table layout matching strategy report style; green accent line; "Open the console" CTA → `CONSOLE_URL`
- `approve_user` route in `admin.py` now sends the branded HTML

**Rejection / access-denied email**
- `render_rejection_html(to_email, display_name)` — same structure, red accent line, polite copy
- `reject_user` route now sends branded HTML with updated subject

**CONSOLE_URL env var**
- `console_url` added to `Settings` (default `http://localhost:9500`)
- `.env.example` documents `CONSOLE_URL` with comment

**Invite email** was already HTML-templated via `render_invite_html` — unchanged.

### Completed (admin user management hardening — 2026-04-16)

**Fix 2 — Delete/revoke invite**
- `DELETE /admin/invites/{invite_id}` — admin-scoped; 404 if not found
- `InviteRepository.delete()` + `get_by_id()` methods
- Frontend: `[inviteId]/route.ts` DELETE proxy; "Revoke" button with inline confirm in `pending-users-panel.tsx`

**Fix 3 — Resend invite**
- `AppInviteModel` gains nullable `sent_at` column (auto-added by `apply_schema_updates`)
- `POST /admin/invites/{invite_id}/resend` — re-sends email, updates `sent_at`
- Frontend: `[inviteId]/resend/route.ts`; "Resend" button with 5s disable + badge in `pending-users-panel.tsx`

**Fix 4 — Change user role**
- `POST /admin/users/{user_id}/set-role` — 409 if targeting self
- `UserRepository.set_app_role()` + `get_by_id()` methods
- Frontend: `[userId]/set-role/route.ts`; "Make admin" / "Make user" toggle in `admin-users-panel.tsx` (own row disabled)

**Fix 5 — Suspend user**
- `POST /admin/users/{user_id}/suspend` — 409 if targeting self; `ApprovalStatus.SUSPENDED` already existed
- Console layout already redirects `suspended` → `/access-denied`
- Frontend: `[userId]/suspend/route.ts`; "Suspend" button with inline confirm (own row excluded)

**Fix 6 — Expandable user detail rows (UI only)**
- Click any row in `admin-users-panel.tsx` to expand: email, role, approval, timestamps, Clerk ID + "Copy user ID"

**Tests:** 5 new backend tests → 146 total
**Runbook:** Section 11 added — full user management action reference

### Completed (branded From display name — 2026-04-16)

**`BRAND_FROM_NAME` env var**
- `brand_from_name: str = "MacMarket Trader"` added to `Settings` in `config.py`
- `ResendEmailProvider` now accepts `from_name` and builds `from_address` as `"Name <email>"` (falls back to bare email when name is empty)
- `build_email_provider()` in `registry.py` passes `settings.brand_from_name` to `ResendEmailProvider`
- `.env.example` documents `BRAND_FROM_NAME=MacMarket Trader` with inbox display comment
- Applies to all outbound emails: invites, approvals, rejections, strategy reports

### Completed (email logo URL + Task Scheduler — 2026-04-15)

**Email logo URL (Fix 1)**
- `_logo_img()` in `email_templates.py` checks `BRAND_LOGO_URL` env var first; falls back to base64 embed, then CSS lockup — no broken image ever rendered
- `BRAND_LOGO_URL` in `config.py` and `.env.example` — defaults to GitHub raw asset URL, can be overridden

**Windows Task Scheduler (Fix 2)**
- `scripts/deploy_windows.bat` prints `[WARN]` reminder if `MacMarket-StrategyScheduler` task is not registered
- `docs/private-alpha-operator-runbook.md` Section 10: schtask register/verify/check/remove commands for 15-minute strategy schedule runner

### Completed (Options B + C — 2026-04-15)

**Option C — Scheduled reports polish (`schedules/page.tsx`)**
- Schedule list: last run relative time + top-candidate badge per row
- Run history rows: scannable "N top · N watch · N no-trade" summary
- Top candidate rows: "Analyze in guided mode →" link to `/analysis?guided=1`
- Empty state: descriptive guidance + "Create your first schedule" CTA with scroll-to-form ref
- Backend `last_run_at` + `top_candidate_count` already present — no changes needed

**Option B — Operational readiness (5 audits, all pass or fixed)**
- Audit 1 (deploy script): PASS — current, no changes
- Audit 2 (runbook): UPDATED — Phase 1 refs → Phase 5/6, full guided flow walkthrough, close-trade lifecycle, new Section 8 (Clerk config requirements), new Section 9 (second operator onboarding checklist — 6 steps)
- Audit 3 (invite flow): PASS — no code gaps, config requirements documented
- Audit 4 (data isolation): ALL PASS — 7/7 entities scoped by `app_user_id`: recommendations, replay_runs, orders, paper_positions, paper_trades, onboarding_status, strategy_schedules
- Audit 5 (empty states): FIXED — dashboard 4 cards + replay/orders tables now show operator-useful hint rows for zero-data new operators

**Options/crypto research preview surfacing**
- Analysis market mode selector: "Options (research preview)" / "Crypto (research preview)" labels + full preview notice paragraph (not bare badge)
- Analysis guided CTA: disabled with inline reason when non-equity mode selected
- Recommendations page: `isPreviewMode` gate — shows preview notice card with restart link, hides all workflow content (queue, hero, grids, chart)
- Dashboard: dismissible `op-card` notice explains equities vs. preview modes; localStorage key `macmarket-preview-modes-noted` suppresses after first dismiss

**Polygon.io live market data — wired and verified**
- `ProviderUnavailableError` exception added to `market_data.py` — raised by `PolygonMarketDataProvider` on HTTP/connection/timeout errors; caught by `MarketDataService` to trigger fallback
- `_fetch_url` helper refactored from `_request_json`; pagination in `get_historical_bars` follows `next_url` (max 3 pages) to collect full `limit` bars
- `health_check` simplified to single snapshot probe (was two calls); catches `ProviderUnavailableError`
- `.env.example` market data section now has full comment block with Polygon free tier note and opt-in instructions
- `docs/local-development.md` has new "Live market data via Polygon.io" subsection with setup, UI changes, and verification steps

---

## Important implementation constraints

- Order `side` field uses `Direction` enum: `"long"` (not `"buy"`) and `"short"` (not `"sell"`). Check `order.side.value == "long"` for buy-side position creation.

## Open Items

### Priority: high value (next build)
- Email delivery: verify Resend adapter works end-to-end for scheduled report delivery to a real inbox (logo URL configurable via `BRAND_LOGO_URL`, From display name configurable via `BRAND_FROM_NAME`)

### Priority: polish
- HACO workspace: deeper indicator controls and signal visibility
- `atm_straddle_mid` expected-range method (contract-allowed, not yet emitted)

---

## Not started (do not touch without explicit authorization)

- Options/crypto replay mode-native semantics
- Full options chain / IV surface / Greeks provider integration
- Crypto venue funding/basis/OI live data
