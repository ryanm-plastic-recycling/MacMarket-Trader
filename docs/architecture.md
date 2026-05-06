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

## Current architecture summary (Phase 6+ private-alpha state)

This is the operating shape of the system as of the 2026-05-05 audit-fix pass.
Detail lives in the named design docs; the items below are the surface area
contract reviewers should know exists.

### Market-mode contract

Every workflow payload (Analysis setup, Recommendations queue/promote, Replay
request/response, Schedule definitions, Orders) carries a typed `market_mode`
(`equities` | `options`) and, where relevant, an `instrument_type`. Replay/live
parity is enforced **within each mode**: equity logic does not apply to
options paths and vice versa. Crypto is reserved as a future mode and is not
implemented.

### Provider / fallback truth

Provider/source state is exposed as three explicit fields rather than a single
"is provider working?" boolean:

- `configured_provider` (`polygon`, `alpaca`, `fallback`)
- `effective_read_mode` (`provider` vs `fallback` for the current request)
- `workflow_execution_mode` (`provider`, `demo_fallback`, `blocked`)

Operator UI (Provider Health, Recommendations, Replay, Orders, Analysis) and
backend payloads agree on these fields so a degraded provider never silently
masquerades as live data. `WORKFLOW_DEMO_FALLBACK=false` blocks workflow
execution rather than falling back invisibly.

### RTH normalization

Intraday windows are normalized to U.S. regular trading hours by
`risk_calendar`/intraday helpers and surfaced as session metadata
(`session_policy=regular_hours`). `INTRADAY_RTH_VIOLATION_MODE` controls
whether out-of-session bars produce a `caution` flag or a hard block. Replay
and live recommendation paths use the same normalizer, so research output and
paper output agree on what counts as a session bar. See
`docs/rth-intraday-normalization-design.md`.

### Market Risk Calendar

A deterministic risk calendar (`src/macmarket_trader/risk_calendar/`) classifies
the day as `clear` | `caution` | `restricted` | `no_trade` based on macro
events, earnings windows, high-volatility flags, and (since 2026-05-04) index
context (VIX level/change, SPX downside, NDX/RUT underperformance). The
calendar is surfaced on Dashboard, Analysis Packet, Recommendations detail,
and email reports. It does not have decision authority by itself — it gates
the deterministic risk engine. See `docs/market-risk-calendar-design.md`.

### Index-aware risk

`src/macmarket_trader/index_risk.py` extracts deterministic signals from
provider-backed index bars and feeds them into the risk calendar. Missing
index bars produce `caution`, never `no_trade`-from-data-absence. LLMs
receive index context as explanation-only provenance; they never get
decision authority over risk gating.

### Options paper lifecycle

Defined-risk option structures (verticals, condors, butterflies) flow through:

1. Research preview (chain-aware, read-only).
2. Read-only / non-persisted expiration-payoff preview.
3. Paper open (`POST /user/options/paper-structures/open`) — multi-leg, with
   contract-commission net P&L and operator risk UX.
4. Manual close (`POST .../close`) — explicit confirmation required.
5. Manual paper-only expiration settlement (`POST .../settle-expiration`) —
   requires literal `SETTLE` confirmation, current-user scoped, no
   automation, no live exercise/assignment, no broker behavior.

Live routing, automated settlement, assignment/exercise, naked shorts,
persisted options recommendations, and options replay persistence into
equity replay are explicitly out of scope. See
`docs/options-paper-lifecycle-design.md`.

### Options review / settlement

Active option positions are reviewed in the same Active Position Review
surface as equities, with options-specific lifecycle fields (legs, DTE,
breakevens, max P/L, contract commissions). Manual close and manual
expiration settlement are operator-confirmed actions, never automated.

### Active position review

The Active Paper Position Review surface (`/orders` and lineage views)
threads the same lineage IDs as guided mode (`recommendation`, `replay_run`,
`order`, `position`) and reuses the deterministic risk engine to flag stops,
targets, time-stops, and stale data. Reopen-closed-position is allowed
within a 5-minute window. See `docs/active-paper-position-management-design.md`.

### AnalysisPacket

`src/macmarket_trader/analysis_packets.py` builds a deterministic packet that
bundles regime, risk-calendar verdict, technical context, indicator context,
expected range, options structure context (when applicable), index context,
and provider/source/as-of provenance. The packet is the canonical input
shared between Recommendations detail UI, scheduled report emails, and the
read-only LLM explanation layer. LLMs never edit or replace packet fields.

### Deployed smoke / evidence layer

`scripts/` contains a release-gate runner, evidence generators, and a
deployed-browser Playwright smoke that drives `https://macmarket.io` either
via a Cloudflare Access service token or via a stored Playwright
storage-state for an approved test user. The deployed smoke is an evidence
artifact, not a routing path: it does not place or modify orders. Compliance
artifacts under `docs/compliance/` and any Phase 11 / 11B / 12 outputs are
**scaffolding only** — directory structure, templates, and dry-run scripts —
not signed compliance evidence or buyer-grade diligence material.

### Hard product boundaries (always true)

- **No live trading.** `LIVE_TRADING_ALLOWED=false` is the default. Any
  non-mock `BROKER_PROVIDER` is refused at the registry factory and again
  inside `AlpacaBrokerProvider.place_paper_order` before any HTTP request is
  made.
- **No broker routing of any kind today**, including Alpaca paper.
- **No automated exits, rolls, or adjustments.** All closes/settlements are
  operator-confirmed.
- **LLMs explain only.** Trade existence, entries, invalidation, targets,
  sizing, and routing are deterministic.
- **Local DB is source of truth** for `approval_status` and `app_role`;
  Clerk is the identity boundary only.

