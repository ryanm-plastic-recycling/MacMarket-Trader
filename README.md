# MacMarket-Trader

MacMarket-Trader is a research-first, event-driven trading system for U.S. large-cap equities and liquid sector ETFs.

## Guardrails

- LLMs are limited to extraction, classification, summarization, and explanation.
- Deterministic engines own trade existence, entries, invalidation, targets, sizing, and routing.
- v1 scope is paper-only execution.
- No crypto or options execution in v1.

## What is included now

- FastAPI deterministic recommendation and replay APIs.
- Stateful replay that evolves portfolio heat/notional per approved fill.
- SQLAlchemy persistence for recommendations, evidence, orders, fills, replay runs/steps, audit logs, provider tables, and app users.
- PostgreSQL-first direction with Alembic migration scaffolding.
- App-level auth/approval model (`pending`, `approved`, `rejected`, `suspended`) and admin approval APIs.
- Email adapter architecture (console + Resend placeholder adapter).
- Product/admin frontend scaffold in `apps/web` (Next.js App Router + TypeScript + Clerk integration boundary).
- Windows deployment and restart scripts in `scripts/`.

## Product/Admin surface in scope

Admin portal, account system, and approval email notifications are now part of the product/admin surface.

## Still out of scope

- Live broker execution
- Generic LLM signal generation
- Consumer-marketing UI features

## Local commands

```bash
# backend setup
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# database
alembic upgrade head

# backend api
uvicorn macmarket_trader.api.main:app --reload --port 9510

# frontend
cd apps/web
npm install
npm run dev

# tests
cd /workspace/MacMarket-Trader
pytest
```
