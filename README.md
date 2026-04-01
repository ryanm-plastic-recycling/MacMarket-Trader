# MacMarket-Trader

MacMarket-Trader is a **private-alpha operator platform** for deterministic, event-driven swing recommendations in U.S. large-cap equities and liquid sector ETFs.

## System purpose

Build a research/live-parity system that can:
1. ingest timestamped market and company events,
2. normalize them into structured features,
3. run deterministic regime/setup/risk engines,
4. produce auditable paper-trading recommendations,
5. measure replay/live behavior using the same core decision path.

## Core design principle

**LLMs extract and explain. Deterministic engines decide and route.**

LLMs are constrained to:
- extraction,
- classification,
- summarization,
- explanation.

LLMs are not used to decide trade existence, entries, invalidation, targets, sizing, or routing.

## Investment mandate

- Universe: U.S. large-cap equities + liquid sector ETFs only
- Style: event-driven swing
- Horizon: 1–5 trading days
- Mode: paper-only in v1
- Session: regular-hours assumptions
- Product stage: operator-facing private alpha

## Explicit non-goals

- Crypto/options expansion in v1
- Consumer/social product features
- Generative “auto trader” behavior
- Non-auditable black-box trade decisions
- UI polish ahead of deterministic engine credibility

## Recommendation contract

Every recommendation must include:
- thesis and catalyst context,
- regime context,
- deterministic entry/invalidation/targets,
- time stop and sizing,
- explicit approval/no-trade outcome,
- evidence + engine versions for auditability.

## Architecture pipeline

```text
Raw ingest -> normalization -> regime engine -> setup engine -> risk engine
-> recommendation record -> OMS intent -> paper broker -> replay/audit persistence
```

## Subsystem requirements

- Provider boundaries (auth/email/data) must be factory-selected from config.
- App-level auth approval and admin role checks are enforced in backend routes.
- Replay must persist per-step snapshots (pre and post state).
- Recommendation quality gates must support explicit no-trade outcomes.
- Backend and frontend should remain typed/testable with minimal vendor coupling.

## Success criteria

- Protected operator routes require approved users.
- Admin flows remain admin-only + MFA-gated by config.
- Replay persistence shows evolving portfolio state per step.
- Low-quality setups can be deterministically rejected as no-trade.
- Provider selection is configurable (mock/console locally, clerk/resend boundary for real wiring).

## Legacy-code policy

See `docs/legacy-policy.md`. In short: new scaffolding should preserve deterministic philosophy and avoid hidden coupling that blocks research/live parity.

## Current scaffold status

Implemented now:
- FastAPI routes for health, recommendations, replay, user/admin approval actions.
- Deterministic regime/setup/risk engines and paper broker flow.
- SQLAlchemy persistence for recommendations, orders/fills, replay, audit, users, email logs.
- Provider registry for auth/email and Clerk/Resend boundaries.
- Next.js operator shell with Clerk integration boundary and approval-oriented pages.

Still missing for production-grade alpha:
- Real upstream market/news ingestion providers,
- richer portfolio/risk controls,
- full provider health dashboards,
- hardened deployment observability and incident workflows.

## Local quickstart

### Backend

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m uvicorn macmarket_trader.api.main:app --reload --port 9510
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

### Tests

```bash
pytest
```

### Windows private-alpha deployment

Use canonical scripts under `scripts/`:
- `scripts/deploy_windows.bat`
- `scripts/restart_windows.bat`
- `scripts/run_backend_dev_windows.bat`
- `scripts/run_frontend_dev_windows.bat`

See `docs/windows-deployment.md` for expected paths/ports and safety behavior.
