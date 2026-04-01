# Architecture Overview

MacMarket-Trader is a deterministic, event-driven research and paper-execution platform for U.S. large-cap equities and liquid sector ETFs.

## Deterministic constraints

- LLMs are restricted to extraction, classification, summarization, and explanation.
- Trade existence, entries, invalidation, targets, sizing, and routing remain deterministic.
- Paper execution only in v1.

## Pipeline

1. Raw ingest (`raw_ingest_events`) and normalization (`normalized_events`, `event_entities`).
2. Regime + setup + risk engines produce deterministic recommendations.
3. Recommendation, evidence, order, fill, audit, portfolio, and replay state persist to SQL.
4. Replay reuses the live recommendation path and advances portfolio state per approved fill.
5. Frontend (Next.js + Clerk) calls FastAPI backend; backend enforces app-level approval and roles from local DB.

## Storage direction

- PostgreSQL-first runtime target.
- SQLite allowed for unit tests.
- Alembic migration scaffolding included.

## Core tables

- ingest/normalization: `raw_ingest_events`, `normalized_events`, `event_entities`, `daily_bars`, `macro_calendar_events`
- provider ops: `provider_cursors`, `provider_health`
- trading/audit: `recommendations`, `recommendation_evidence`, `orders`, `fills`, `portfolio_snapshots`, `replay_runs`, `replay_steps`, `audit_logs`
- product/admin: `app_users`, `user_approval_requests`, `email_delivery_logs`

## HACO/HACOLT in current architecture

HACO and HACOLT are integrated as deterministic indicator context and operator charting payloads. They are intentionally secondary to event/regime/risk approval logic.

- Backend chart contract: `/charts/haco` (approved users only).
- Recommendation context includes HACO state, flip recency, HACOLT direction, and side agreement.
- Core recommendation approval remains quality-gated event/regime/risk logic.

