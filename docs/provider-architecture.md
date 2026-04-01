# Provider Architecture

MacMarket-Trader keeps vendor SDKs behind interface boundaries so deterministic engines remain stable and testable.

## Provider interfaces

- `MarketDataProvider`
- `NewsProvider`
- `MacroCalendarProvider`
- `BrokerProvider` (paper-only in v1)
- `EmailProvider`
- `AuthProvider`

## Factory selection

Provider mode is selected from config:

- `AUTH_PROVIDER=mock|clerk`
- `EMAIL_PROVIDER=console|resend`

Default local mode is `mock` + `console`.

## Current adapters

- Auth: `MockAuthProvider`, `ClerkAuthProvider`
- Email: `ConsoleEmailProvider`, `ResendEmailProvider`

## Persistence support tables

Provider health, cursors, raw ingest, normalized events, entities, and email logs are persisted in SQLAlchemy models and migration scaffolding.
