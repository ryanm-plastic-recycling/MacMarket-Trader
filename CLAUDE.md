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

**CURRENT STATE: Phases 0–6 complete. 141 backend tests. 8 Playwright e2e. tsc clean.**

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
- Email delivery: verify Resend adapter works end-to-end for scheduled report delivery to a real inbox

### Priority: polish
- HACO workspace: deeper indicator controls and signal visibility
- `atm_straddle_mid` expected-range method (contract-allowed, not yet emitted)

---

## Not started (do not touch without explicit authorization)

- Options/crypto replay mode-native semantics
- Full options chain / IV surface / Greeks provider integration
- Crypto venue funding/basis/OI live data
