# Local Development

## Environment files (separate backend vs frontend)

- Repo-root `.env` is for **backend FastAPI settings** (loaded by `src/macmarket_trader/config.py`).
- `apps/web/.env.local` is for **Next.js server/runtime settings**.
- Start from the checked-in templates:
  - `cp .env.example .env`
  - `cp apps/web/.env.local.example apps/web/.env.local`


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

Fallback behavior is always preserved: if Polygon/Alpaca calls fail, backend chart/snapshot reads automatically revert to deterministic fallback bars and the provider-health endpoint reports degraded status.

## Backend (FastAPI)

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

## Frontend runtime/API routing

- Browser calls now use same-origin Next.js route handlers under `apps/web/app/api/*` (no browser localhost dependency).
- Next server route handlers forward to backend origin from `BACKEND_API_ORIGIN` (default `http://127.0.0.1:9510`).
- Backend CORS remains minimal for split-port local development (`http://127.0.0.1:9500`, `http://localhost:9500`), but production browser traffic should use the frontend proxy path.

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

1. `/recommendations` (flagship): generate and review deterministic setups.
2. `/replay-runs`: validate recommendation behavior path-by-path.
3. `/orders`: inspect staged paper fills and blotter state.
4. `/admin/pending-users` and `/admin/users`: invite, approve, and monitor current operator access.
5. `/account`: confirm your own role/approval/MFA posture.

## Reset and host consistency quick checklist

- Clean reset: stop app -> remove local sqlite db -> rerun seed/bootstrap -> restart backend/web.
- Use one hostname consistently in local dev sessions (for example, always `http://localhost:3000`) to avoid cookie/session drift.
- Provider fallback interpretation: when provider is configured but unavailable, workflows explicitly run in fallback mode and UI badges must declare fallback source.
