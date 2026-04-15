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

**CURRENT PHASE: Phase 5 — Operator console polish (active)**
Phases 0–4: Complete. 137 backend tests passing. `npx tsc --noEmit` clean.

### Completed this session (2026-04-15)

**Fix 1 — WorkflowBanner human-readable chips**
- Composed primary context line (SYMBOL · strategy · market mode)
- Rec/Replay/Order chips now read Rec #N / Replay #N / Order #N
- Source chip reads "via {source}"
- "lineage incomplete" chip renders in amber warning tone

**Fix 2 — Recommendations page guided queue collapse**
- `showQueue` state defaults to collapsed in guided mode
- "View recommendation queue (N)" ghost button toggle added
- Explorer mode unchanged

**Fix 3 — Replay stageability warning block**
- `op-error` styled block renders when `has_stageable_candidate === false`
- Shows `stageable_reason` or default message
- Includes operator note to return to Recommendations

**Fix 4 — Sticky table headers on Replay + Orders history tables**
- Both tables wrapped in scroll containers (320px / 280px max-height)
- `thead th`: position sticky, top 0, z-index 1, card-bg background

**Fix 5 — Save as alternative separated from Make active**
- Backend: `promote_queue_candidate` reads `action` field (`make_active` / `save_alternative`)
- Frontend: `saveAlternative()` wired with `action: "save_alternative"`
- `promoteSelected()` explicitly sends `action: "make_active"`
- Mutual-exclusion disabled states applied during in-flight requests
- Test: `test_user_ranked_queue_candidate_can_be_saved_as_alternative` passing

**README.md:** Updated to reflect Phase 5 as active scope.

**Fix 6 — TopbarContext dynamic active-context line**
- Created `components/topbar-context.tsx` (client component, Suspense-wrapped)
- Topbar now shows `SYMBOL · strategy` in guided mode, "Guided workflow — start at Analyze" with no symbol, "Explorer mode" when not guided
- Replaces static "Workflow: Analyze → Recommendation → Replay → Paper Order" span

**Fix 7 — Role-gated Admin sidebar section**
- `console-shell.tsx` fetches `/api/user/me` on mount; Admin nav section hidden until `app_role === "admin"` (null state renders nothing, no flash)

**Fix 8 — BUY/SELL side badge color in order detail panels**
- `orders/page.tsx` guided hero and detail panel now use `<StatusBadge tone="good">` for BUY, `tone="warn"` for SELL (matches existing table row behavior)

**Fix 9 — Replay step row left-border accent by approval**
- `replay-runs/page.tsx` step row: `borderLeft: "3px solid #21c06e"` (approved) / `"3px solid #f44336"` (rejected)

**Fix 10 — Strategy selector description + regime hints**
- Backend `StrategyRegistryEntry` Pydantic model: added `description: str | None = None` and `regime_fit: str | None = None`
- All 6 equities strategies seeded with description and regime_fit values in `strategy_registry.py`
- Frontend `StrategyRegistryEntry` type: added `description?: string` and `regime_fit?: string`
- Analysis page: `selectedStrategyEntry` useMemo + inline description block below Strategy `<select>` (muted text, description + `· regime_fit`)

---

## Open Items

### Priority: test coverage
- ~~Playwright e2e coverage for guided lineage hero cards, empty-state heroes, and post-create hydration flows~~ **Done** — 8 Playwright e2e tests passing in `guided-workflow-hero.spec.ts` + `phase1-closeout.spec.ts` (see roadmap-status.md 2026-04-15 e2e pass)
- Component-level frontend tests for guided hero variants beyond current e2e coverage

---

## Not started (Phase 6 scope — do not touch yet)

- Options/crypto replay mode-native semantics
- `atm_straddle_mid` expected-range method
- Full close-trade lifecycle accounting (`paper_positions` / `paper_trades` scaffold exists, UI not built)
