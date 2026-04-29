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
  api/routes/admin.py                    — protected user + admin route handlers
  api/routes/analysis.py                 — strategy workbench backend
  replay/engine.py                       — deterministic replay runner
  recommendation/service.py              — recommendation generation
  indicators/                            — HACO/HACOLT indicator math
  execution/                             — broker scaffolds (mock + AlpacaBrokerProvider)
apps/web/
  app/(console)/                         — operator console pages
    analysis/page.tsx                    — Strategy Workbench
    recommendations/page.tsx             — Recommendations workspace
    replay-runs/page.tsx                 — Replay workspace
    orders/page.tsx                      — Paper Orders workspace
    settings/page.tsx                    — user settings
    welcome/page.tsx                     — alpha welcome guide
  components/
    workflow-banner.tsx                  — guided flow context chip bar
    guided-step-rail.tsx                 — step 1–4 rail navigation
    active-trade-banner.tsx              — sticky trade context (guided mode)
    brand-header.tsx                     — pre-auth brand header
  lib/
    guided-workflow.ts                   — guided state parse/build helpers
    recommendations.ts                   — queue/provenance helpers
    lineage-format.ts                    — display_id formatting
    orders-helpers.ts                    — PnL + duration helpers
docs/alpha-user-welcome.md               — canonical welcome doc (rendered at /welcome)
docs/roadmap-status.md                   — full phase history
docs/private-alpha-operator-runbook.md   — deployment runbook
scripts/run-due-schedules.ps1            — scheduler wrapper
scripts/backup-db.ps1                    — daily DB backup
tests/                                   — backend pytest suite
apps/web/tests/e2e/                      — Playwright e2e suite
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

# Run due scheduled reports (also wired to MacMarket-StrategyScheduler task)
python -m macmarket_trader.cli run-due-strategy-schedules

# Poll Alpaca paper fills (Phase 9 — not yet active)
python -m macmarket_trader.cli poll-alpaca-fills
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

Primary operator path: **Analyze → Recommendation → Replay → Paper Order → Position → Close**.

Context threads through URL query params: `guided=1`, `symbol`, `strategy`, `market_mode`, `source`, `recommendation` (UID), `replay_run` (ID), `order` (ID).

`WorkflowBanner` (`components/workflow-banner.tsx`) renders the active lineage as chips and prefers `display_id` over the canonical `rec_<hex>`.
`ActiveTradeBanner` (`components/active-trade-banner.tsx`) is a sticky top strip in guided mode showing SYMBOL · strategy · `display_id` · status.
`GuidedStepRail` renders the 1–4 step rail.
`parseGuidedFlowState` / `buildGuidedQuery` in `lib/guided-workflow.ts` are the canonical helpers.

In guided mode: "Make active" auto-advances to `/replay-runs`, "Run replay now" auto-advances to `/orders` (skipped if `has_stageable_candidate=false`). "Stage paper order now" is the terminal step. Cancel staged order is allowed pre-fill; reopen closed position is allowed within a 5-minute window.

---

## Important implementation constraints

- `user_is_approved=True` must be passed to `recommendation_service.generate()` during replay so quality-gate overrides apply and `has_stageable_candidate` is computed correctly.
- Order `side` field uses `Direction` enum: `"long"` (not `"buy"`) and `"short"` (not `"sell"`). Check `order.side.value == "long"` for buy-side position creation.
- Promote endpoint (`/user/recommendations/queue/promote`) accepts `action` field (`make_active` / `save_alternative`) — stored in `ranking_provenance` and returned in response.
- `display_id` format: `{SYMBOL}-{STRATEGY_ABBREV}-{YYYYMMDD}-{HHMM}`. Generated at recommendation creation. Falls back to `display_id_or_fallback()` for legacy rows (returns `Rec #shortid`). Canonical `recommendation_id` (`rec_<hex>`) stays the unique key — `display_id` is a label only, never used as FK.
- `console_url` in `config.py` is a `@property` that mirrors `app_base_url`. Do not add a separate `CONSOLE_URL` env var.
- `apply_schema_updates()` handles all new columns automatically on startup. No manual Alembic migrations needed for nullable columns.
- Identity reconciliation: `upsert_from_auth` matches by Clerk sub, then by email, then by `invited::email` prefix. Preserves `approval_status` and `app_role` through merge.
- `BROKER_PROVIDER=mock` is the current production setting. Do not change to `alpaca` without completing Phase 9.
- Sticky `thead th` pattern: inline styles `position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)"`.
- `op-error` block style: `border: 1px dashed #7c4040; background: #2a1717`.

---

## Current Phase Status

**CURRENT STATE: Phases 0–6 + Pass 4 complete. Private alpha live at https://macmarket.io. 3 alpha users. Phase 9 (Alpaca paper integration) is next.**

Tests (2026-04-29): pytest 210, vitest 99, Playwright 31 (all passing, 0 skipped). tsc clean.

Deployment: `https://macmarket.io` via Cloudflare Tunnel; backend `uvicorn` on `127.0.0.1:9510`; frontend Next.js on `0.0.0.0:9500`; SQLite at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db`; daily 3 AM backup via `MacMarket-DB-Backup` task; strategy scheduler every 5 min via `MacMarket-StrategyScheduler` task.

Phase 6 + Pass 4 ships the full Analyze → Recommendation → Replay → Paper Order → Position → Close workflow with cancel-staged + reopen-closed (5 min) lifecycle, `display_id` labels (`AAPL-EVCONT-20260429-0830`), per-user `risk_dollars_per_trade` + Settings page at `/settings`, welcome guide at `/welcome` with brand header on pre-auth pages, invite email with welcome CTA, timezone-aware schedules, role-conditional sidebar, sticky Active Trade banner, auto-advance guided CTAs, Polygon market data (equities live; options chain preview research-only), and Cloudflare Access invite-only enforcement. See `docs/roadmap-status.md` for full phase history.

---

## Open Items (Phase 9 is next)

### Phase 9 — Alpaca paper integration (NEXT)
Wire `BROKER_PROVIDER=alpaca` for real paper fills. Keys configured in deployed `.env`: `APCA_API_KEY_ID=PK...`, `APCA_API_SECRET_KEY=...`, `ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets`. Scaffold exists in `src/macmarket_trader/execution/`. `AlpacaBrokerProvider` needs: `place_order`, `get_order`, `cancel_order`, `get_account`. Fill polling via CLI `poll-alpaca-fills`, run every 5 min via existing scheduler script.

### Phase 7 — Brokerage fees + commission modeling
`gross_pnl` / `net_pnl` split in `paper_trades`. Per-contract options commission (default `$0.65`). Per-trade equity commission (default `$0`). Commission settings in user Settings page.

### Phase 8 — Options execution (research → paper parity)
8A: Options replay. 8B: Options paper orders with expiry tracking. 8C: Greeks + IV display. 8D: IV rank as Iron Condor strategy gate. Prerequisite: Phase 7 commission model.

### Phase 10 — Crypto
Crypto-native strategy design + paper execution via Alpaca. Prerequisite: user specifies desired strategies before build.

### Known gaps (no phase assigned)
- `/account` page does not render Clerk `<UserProfile>` for MFA enrollment (Clerk MFA requires paid plan — deferred)
- `MacMarket-Strategy-Reports` scheduled task may be redundant with `MacMarket-StrategyScheduler` — verify and delete if duplicate
- `display_id` collision if two recs created for same symbol+strategy within same minute — needs suffix handling
- npm vitest/vite/esbuild moderate vulns (dev-server only, not production) — deferred until vitest 4 migration
- `save_alternative` backend action variant not yet implemented (UI button exists, disabled)
- `atm_straddle_mid` expected-range method not yet emitted
- Options/crypto replay and paper orders blocked at research-preview only — Phase 8 addresses this
- Invite reconciliation: manually patched for current alpha users; `upsert_from_auth` handles it going forward but verify with next new-user signup
