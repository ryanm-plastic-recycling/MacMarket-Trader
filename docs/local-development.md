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

Create a lean shareable archive (excluding runtime artifacts) with the canonical backup script: `scripts\\create_shareable_backup.bat`.
