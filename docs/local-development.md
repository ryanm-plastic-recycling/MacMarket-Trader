# Local Development

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

## Test suite

```bash
pytest -q
```

## Frontend runtime/API routing

- Browser calls now use same-origin Next.js route handlers under `apps/web/app/api/*` (no browser localhost dependency).
- Next server route handlers forward to backend origin from `BACKEND_API_ORIGIN` (default `http://127.0.0.1:9510`).
- Backend CORS remains minimal for split-port local development (`http://127.0.0.1:9500`, `http://localhost:9500`), but production browser traffic should use the frontend proxy path.
