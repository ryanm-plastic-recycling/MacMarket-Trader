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

# Poll Alpaca paper fills (future execution phase — not yet active)
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
- `BROKER_PROVIDER=mock` is the current production setting. Do not change to `alpaca` without a later explicit execution phase.
- Sticky `thead th` pattern: inline styles `position: "sticky", top: 0, zIndex: 1, background: "var(--card-bg)", borderBottom: "1px solid var(--table-border)"`.
- `op-error` block style: `border: 1px dashed #7c4040; background: #2a1717`.

---

## Current Phase Status

**CURRENT STATE: Phases 0–9 complete for the current private-alpha/options parity scope. Private alpha live at https://macmarket.io. 3 alpha users. Phase 10 is now the safe planning/polish track for remaining deferred options/provider/crypto work; 10A1 is complete for Analysis Expected Range visualization reuse, 10B1 is complete for Orders durable paper-options display/readability polish, and 10C1 is complete for the explainable metric glossary foundation; live/broker execution is not active.**

Tests (2026-04-30): pytest 210, vitest 174, Playwright 31 (all passing, 0 skipped). tsc clean.

Phase 10C2 is complete for compact Recommendations score/risk-label help using
the existing glossary and `MetricLabel` foundation. Broader Analysis, Replay,
Orders, and glossary-page rollout remains open; scoring, provider behavior,
backend behavior, lifecycle math, payoff math, commission math, equity
behavior, schema, and execution semantics did not change.

Phase 10C3 is complete for compact Orders P&L/commission-label help using the
existing glossary and `MetricLabel` foundation. Broader Analysis, Replay, and
glossary-page rollout remains open; no Orders actions, backend behavior,
scoring, provider behavior, lifecycle math, payoff math, commission math,
equity behavior, schema, or execution semantics changed.

Phase 10C4 is complete for compact Analysis and Replay metric-label help using
the existing glossary and `MetricLabel` foundation. The rollout adds help to
Analysis options risk/source labels and Replay score/confidence/P&L/fee labels
without changing recommendation scoring, replay behavior, backend behavior,
lifecycle math, payoff math, commission math, equity behavior, schema, or
execution semantics. A broader glossary/reference page remains open.

Deployment: `https://macmarket.io` via Cloudflare Tunnel; backend `uvicorn` on `127.0.0.1:9510`; frontend Next.js on `0.0.0.0:9500`; SQLite at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db`; daily 3 AM backup via `MacMarket-DB-Backup` task; strategy scheduler every 5 min via `MacMarket-StrategyScheduler` task.

Phase 6 + Pass 4 ships the full Analyze → Recommendation → Replay → Paper Order → Position → Close workflow with cancel-staged + reopen-closed (5 min) lifecycle, `display_id` labels (`AAPL-EVCONT-20260429-0830`), per-user `risk_dollars_per_trade` + Settings page at `/settings`, welcome guide at `/welcome` with brand header on pre-auth pages, invite email with welcome CTA, timezone-aware schedules, role-conditional sidebar, sticky Active Trade banner, auto-advance guided CTAs, Polygon market data (equities live; options chain preview research-only), and Cloudflare Access invite-only enforcement. Phase 7 is closed for equity paper-readiness, Phase 8 is closed for the scoped paper-first options capability, and Phase 9 is closed for current options provider/source/as-of parity plus Recommendations Expected Range visualization. See `docs/roadmap-status.md` for full phase history.

---

## Open Items (Phase 10 planning/polish is next)

### Phase 10 — Deferred-work planning and safe options polish (NEXT)
Phase 10 organizes remaining deferred items before risky implementation. Planned subphases: `10A` options UX/operator polish, `10B` durable Orders parity polish, `10C` options replay/history design checkpoint, `10D` expiration-settlement design checkpoint, `10E` provider-depth/readiness planning, `10F` crypto architecture planning only, and `10G` closure. `10A1` is complete for frontend-only Analysis Expected Range visualization using existing payload fields and the existing reusable component; `10B1` is complete for frontend-only Orders durable paper-options display/readability polish using existing lifecycle fields only; `10C1` is complete for the frontend-only central glossary registry and reusable metric-help foundation; `10C2` through `10C4` are complete for compact Recommendations, Orders, Analysis, and Replay metric-help rollout. Broader `10A`/`10B`, optional glossary/reference-page work, and replay/history design work remain open.

### Later execution phase — Alpaca paper integration (NOT ACTIVE)
Wire `BROKER_PROVIDER=alpaca` only after a later explicit execution phase. Keys are configured in deployed `.env`, and scaffold exists in `src/macmarket_trader/execution/`, but real brokerage routing/execution remains disabled. Fill polling via CLI `poll-alpaca-fills` is not active.

### Phase 7 — Brokerage fees + commission modeling
Closed for the current equity paper-readiness scope. `gross_pnl` / `net_pnl`, per-trade equity commission, per-contract options commission settings, and current fee display guardrails are documented in `docs/roadmap-status.md`.

### Phase 8 — Options research → paper parity
Closed for the current scoped paper-first options capability: research preview, read-only/non-persisted payoff preview, supported defined-risk paper open/manual-close lifecycle, contract-commission net P&L, and Recommendations operator risk UX. Expiration settlement, assignment/exercise automation, persisted options recommendations, and live routing remain deferred.

### Phase 9 — Options operator parity and data-quality hardening
Closed for the current scope: durable paper-options Orders visibility, provider/source/as-of parity across the current options surfaces, and the Recommendations Expected Range visualization. Analysis visualization later landed in `10A1`; richer replay placement, provider-depth probes, and live routing remain future work only if explicitly reopened.

### Future crypto implementation
Phase 10F may plan crypto architecture only. Crypto implementation, crypto paper execution, and crypto-specific provider wiring remain later work.

### Known gaps (no phase assigned)
- `/account` page does not render Clerk `<UserProfile>` for MFA enrollment (Clerk MFA requires paid plan — deferred)
- `MacMarket-Strategy-Reports` scheduled task may be redundant with `MacMarket-StrategyScheduler` — verify and delete if duplicate
- `display_id` collision if two recs created for same symbol+strategy within same minute — needs suffix handling
- npm vitest/vite/esbuild moderate vulns (dev-server only, not production) — deferred until vitest 4 migration
- `save_alternative` backend action variant not yet implemented (UI button exists, disabled)
- `atm_straddle_mid` expected-range method not yet emitted
- Options remain paper-first only: no live routing, expiration settlement, assignment/exercise automation, naked shorts, persisted options recommendations, or options replay persistence into equity replay flows
- Invite reconciliation: manually patched for current alpha users; `upsert_from_auth` handles it going forward but verify with next new-user signup
