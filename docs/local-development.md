# Local Development

## Environment files (separate backend vs frontend)

- Repo-root `.env` is for **backend FastAPI settings** (loaded by `src/macmarket_trader/config.py`).
- `apps/web/.env.local` is for **Next.js server/runtime settings**.
- Start from the checked-in templates:
  - `cp .env.example .env`
  - `cp apps/web/.env.local.example apps/web/.env.local`

## Auth mode for local dev (explicit mock opt-in)

- Production/deployment examples default to Clerk (`AUTH_PROVIDER=clerk`).
- For local-only mock auth, set both:
  - `ENVIRONMENT=local` (or `dev`/`test`)
  - `AUTH_PROVIDER=mock`
- Startup fails closed if `AUTH_PROVIDER=mock` is used outside `dev/local/test`.


## Market data provider (backend `.env`)

MacMarket-Trader can run in deterministic fallback mode, Polygon mode (preferred), or Alpaca mode (scaffold retained).

- Fallback-only (default):
  - `POLYGON_ENABLED=false`
  - `MARKET_DATA_PROVIDER=fallback`
  - `MARKET_DATA_ENABLED=false`
- Polygon enabled:
  - Create an API key in Polygon dashboard (Stocks API access): https://polygon.io/dashboard/api-keys
  - Set `POLYGON_ENABLED=true`
  - Set `POLYGON_API_KEY=...`
  - Optional: `POLYGON_BASE_URL=https://api.polygon.io`, `POLYGON_TIMEOUT_SECONDS=8`
- Alpaca enabled (kept as alternate scaffold):
  - `POLYGON_ENABLED=false`
  - `MARKET_DATA_PROVIDER=alpaca`
  - `MARKET_DATA_ENABLED=true`
  - `APCA_API_KEY_ID` + `APCA_API_SECRET_KEY`

Fallback behavior is always preserved for chart/snapshot reads. User-facing workflow endpoints (Analysis setup, Recommendations, Replay, Orders) intentionally block when provider-backed data is configured but degraded, so operators do not silently run execution workflows on demo bars.

Local/dev override (explicit):
- `WORKFLOW_DEMO_FALLBACK=true` (backend `.env`) allows workflow endpoints to proceed in fallback mode **only** when `ENVIRONMENT` is `dev`, `local`, or `test`.
- Keep this disabled for production-facing behavior.

## Backend (FastAPI)

MacMarket-Trader backend dependencies are managed from `pyproject.toml` (PEP 621).
There is currently **no root `requirements.txt`** install path.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m uvicorn macmarket_trader.api.main:app --reload --port 9510
```

## Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

## Seed deterministic demo/operator data

```bash
python -m macmarket_trader.cli seed-demo-data
# or:
python scripts/seed_demo_data.py
```

This local/demo seed path adds a minimal-but-usable dataset for the operator dashboard:
- at least one recommendation,
- at least one replay run,
- at least one order/fill,
- at least one pending user,
- provider-health snapshots for auth/email/market data.

## Recommendations workflow (local/dev)

- Recommendations page is data-backed from local `recommendations` records (no placeholder-only mode).
- Use **Generate / Refresh recommendations** on `/recommendations` to trigger a deterministic backend generation run.
- If no rows exist and environment is `dev/local/test`, backend auto-seeds one deterministic recommendation so the detail pane is immediately usable.
- Detail pane surfaces thesis, catalyst, setup, entry zone, invalidation, targets, expected RR, confidence, provenance notes, and approved/no-trade reason.

## HACO alignment expectations

- HACO candles, flip markers (BUY/SELL), HACO strip, and HACOLT strip are all anchored to the same canonical indexed bar series.
- Timeframe switches must keep every chart layer on the same canonical indices (no lookahead/off-by-one shifts between panes).
- Marker placement is tied to the exact bar where the flip state triggers.
- Provider-backed mode and fallback mode both use the same canonical alignment path.

## Invite-based onboarding (private alpha)

- Primary onboarding path is admin invite, not open self-registration.
- Admin invite UI entry point: `/admin/pending-users` → **Private alpha invite** panel.
- In `EMAIL_PROVIDER=console` local mode, the invite payload (including invite link) is logged in backend console output.
- Invited users sign in/up through existing Clerk `/sign-up`/`/sign-in` routes and remain local `pending` until approved.
- Local admin bootstrap:
  1. Sign in as the intended admin user.
  2. Promote local role in DB (`app_role=admin`, `approval_status=approved`) once.
  3. Subsequent logins preserve local `app_role`/`approval_status` (source-of-truth rule).

## Test suite

```bash
pytest -q
```

If local shell defaults to a non-test auth provider through a personal `.env`, force mock-auth test mode explicitly:

```bash
ENVIRONMENT=test AUTH_PROVIDER=mock pytest -q
```

## Frontend runtime/API routing

- Browser calls use same-origin Next.js route handlers under `apps/web/app/api/*`.
- Workflow pages call same-origin routes with session cookies by default; route handlers resolve Clerk session auth server-side first, then optionally accept a bearer token fallback.
- This removes `getToken()` client races that previously caused intermittent stale 401/Invalid token banners even after session recovery.
- Next route handlers still forward to backend origin from `BACKEND_API_ORIGIN` (default `http://127.0.0.1:9510`).

## Runtime reset hygiene (local)

When local runtime state looks stale/inconsistent:

1. Stop frontend and backend dev servers.
2. Clear frontend build cache:
   - macOS/Linux: `rm -rf apps/web/.next`
   - Windows PowerShell: `Remove-Item -Recurse -Force apps/web/.next`
3. Reinitialize dependencies/processes (`npm install`, restart backend/frontend).
4. Reinitialize or reseed local DB as needed:
   - `python -m macmarket_trader.cli init-db`
   - `python -m macmarket_trader.cli seed-demo-data`
5. If deleting SQLite DB file manually, always stop backend/frontend first, then restart backend and reseed.

Create a lean shareable archive (excluding runtime artifacts) with the canonical backup script: `scripts\\create_shareable_backup.bat`.

## Private-alpha operator workflow refresh (2026-04)

- Recommendations is the flagship workspace: generate deterministic recommendations from catalyst text, inspect detail pane, then run replay or stage paper order.
- Replay workspace supports one-click deterministic replay runs and step-by-step heat snapshots.
- Orders page is a paper/dev blotter with staged deterministic orders only.
- Admin invite flow is the primary onboarding path (invite + pending approval + approve/reject).
- Admin users view (`/admin/users`) shows current local users, role/approval truth, MFA, invite state, and last seen metadata.
- Account page surfaces self-service identity + authorization metadata including last seen/last authenticated timestamps.
- Local demo data can be seeded with `python scripts/seed_demo_data.py`.

## Where to start in the UI

1. `/analysis` (Strategy Workbench): choose symbol/timeframe/strategy, inspect levels/context, and create recommendation.
2. `/recommendations`: review deterministic setup detail, source truth, and execution readiness.
3. `/replay-runs`: validate recommendation behavior path-by-path.
4. `/orders`: inspect staged paper fills and blotter state.
5. `/admin/pending-users` and `/admin/users`: invite, approve, and monitor current operator access.
6. `/account`: confirm your own role/approval/MFA posture.

## Reset and host consistency quick checklist

- Clean reset: stop app -> remove local sqlite db -> rerun seed/bootstrap -> restart backend/web.
- Use one hostname consistently in local dev sessions (for example, always `http://localhost:3000`) to avoid cookie/session drift.
- Provider fallback interpretation:
  - provider degraded + `WORKFLOW_DEMO_FALLBACK=false` => workflows are blocked
  - provider degraded + `WORKFLOW_DEMO_FALLBACK=true` (dev/local/test only) => workflows run on explicit demo fallback bars
  - dashboard + provider health expose the same configured/effective/workflow mode truth model.

## Auth readiness and inline operator feedback (2026-04 update)

- Same-origin workflow calls now prioritize server-side session auth (cookie/session) and no longer depend on client token readiness for normal operator flows.
- When Clerk session is present but token materialization is still initializing, same-origin routes return an auth-initializing response and workflow pages remain in loading state instead of surfacing a stale 401/Invalid token banner.
- If session is unavailable, pages show inline retry-capable error feedback and clear stale banners on first subsequent successful fetch.
- Replay/Orders/Recommendations/Admin actions now use non-blocking inline feedback states:
  - loading (in-progress),
  - success (completion),
  - error (with retry).
- Stale error banners are cleared on first subsequent successful fetch to avoid persistent false-failure states.

## Strategy Workbench workflow

- Indicator selector now exposes first-class rendered overlays on Analysis and Recommendations charts:
  - EMA 20, EMA 50, EMA 200
  - VWAP
  - Bollinger Bands
  - Prior day high/low
  - Volume bars
  - RSI compact strip
- Non-rendered indicators remain visible but disabled until implemented to avoid misleading toggle behavior.
- HACO Context restricts indicator selection to HACO/HACOLT strips only; first-class workflow overlays remain on Analysis/Recommendations charts.


- New flagship-adjacent workflow page: `/analysis` (Analysis / Strategy Workbench).
- Operators can select symbol, timeframe, strategy, and review chart + setup levels (entry/stop/targets/trigger/confidence).
- Analysis uses draft controls and only runs protected fetches on **Refresh analysis** (plus one intentional initial load after auth is ready).
- Supported initial strategy menu:
  - Event Continuation
  - Breakout / Prior-Day High
  - Pullback / Trend Continuation
  - Gap Follow-Through
  - Mean Reversion
  - HACO Context (supporting context, not sole approval engine)
- Workbench has CTA: **Create recommendation from this setup**.
- Source coherence is explicit: provider/fallback source chip is displayed and fallback is labeled throughout workflow context.

- Supported Analysis timeframes are currently: `1D`, `4H`, `1H` (no synthetic `1W` option).
- Workflow pages explicitly label source mode as provider, fallback (local/dev override), or provider-blocked.
- Source chips should never display `unknown`; if source is not resolved yet, UI shows `workflow pending`.

## Theme persistence (SSR-safe)

- Theme toggle in top bar persists to:
  - cookie `macmarket-theme` (SSR-safe initial render), and
  - localStorage `macmarket-theme` (client preference continuity).
- Root HTML `data-theme` is seeded server-side from cookie to avoid hydration mismatch.

## Scheduled reports local run

- Set `EMAIL_PROVIDER=console` in `.env`.
- Create schedules from **Scheduled Reports** console page.
- Trigger immediate run with "Run now" or execute `python -m macmarket_trader.cli run-due-strategy-schedules`.
- Console output contains ranked payload sections (`top_candidates`, `watchlist_only`, `no_trade`).

## Roadmap status tracking

- Current alpha roadmap status is tracked in `docs/roadmap-status.md`.
- Treat the current milestone as **Phase 1 — Private alpha hardening** until open Phase 1 items there are closed.
- Operator validation checklist and recovery playbook are in `docs/private-alpha-operator-runbook.md`.
