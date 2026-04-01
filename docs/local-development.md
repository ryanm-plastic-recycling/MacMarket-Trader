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
pytest
```
