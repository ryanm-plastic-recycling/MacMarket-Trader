# Provider Architecture

MacMarket-Trader uses interface-first adapters so deterministic engines are not coupled to vendor SDKs.

## Provider interfaces

- `MarketDataProvider`
- `NewsProvider`
- `MacroCalendarProvider`
- `BrokerProvider` (paper-only in v1)
- `EmailProvider` (Console + Resend adapters)
- `AuthProvider` (Clerk token verification boundary)

Mock providers remain default for local development and deterministic tests.

## Persistence support tables

Provider health, cursors, raw ingest, normalized events, entities, and email logs are persisted in SQLAlchemy models and covered by Alembic migration scaffolding.
