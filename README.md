# MacMarket-Trader

MacMarket-Trader is a **research-first, event-driven trading system scaffold** for U.S. large-cap equities and liquid sector ETFs.

> This is **not** an LLM-autonomous trading bot.

## v1 Scope

- Universe: U.S. large-cap equities + liquid sector ETFs
- Holding period: 1–5 trading days
- Session: regular-hours only
- Execution: paper-trading first
- Decisioning: deterministic setup/risk/portfolio/execution logic
- LLM role: extraction/summarization/explanation only
- Architecture priority: audit-first and replayable from day one

## What this repository does today

This scaffold implements a deterministic path:

`market/news context -> structured event -> regime context -> trade setup -> sizing -> order intent -> paper execution -> attribution`

The first milestone is a credible recommendation pipeline, **not** a dashboard.

## Core Architecture

- **FastAPI** for API delivery (`/health`, `/recommendations/generate`, `/replay/run`)
- **Pydantic v2** domain schemas
- **SQLAlchemy 2.x** model base with SQLite default and Postgres-compatible patterns
- **Deterministic engines** for regime, setup, risk, portfolio, replay, and audit
- **Mock LLM extractor** for structured event extraction (no trade decision authority)

See `docs/architecture.md` for details.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
pytest
uvicorn macmarket_trader.api.main:app --reload
```

## Non-goals in this milestone

No React frontend, no dashboard pages, no auth/admin, no Discord bot, no crypto/options support, and no legacy HACO application code in the core path.

## Legacy policy

Old MacMarket code is reference-only. See `docs/legacy-policy.md`.
