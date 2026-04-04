# Private Alpha Operator Runbook (Phase 1)

Last updated: 2026-04-04

This runbook is for internal operators validating the **Phase 1 product center**:

1. Analysis / Strategy Workbench
2. Recommendations
3. Replay
4. Paper Orders
5. Provider Health truth checks

## 1) Local start checklist

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m uvicorn macmarket_trader.api.main:app --reload --port 9510
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

### Seed deterministic operator data

```bash
python -m macmarket_trader.cli init-db
python -m macmarket_trader.cli seed-demo-data
```

## 2) Provider mode vs fallback mode (must stay explicit)

Provider/source truth is represented in three fields:

- **configured provider** (`polygon`, `alpaca`, or `fallback`)
- **effective read mode** (`provider` read path or fallback read path)
- **workflow execution mode** (`provider`, `demo_fallback`, or `blocked`)

### Interpretation rules

- `workflow_execution_mode=provider`
  - Recommendations, Replay, and Orders are running on provider-backed bars.
- `workflow_execution_mode=blocked`
  - Provider probe failed and `WORKFLOW_DEMO_FALLBACK=false`.
  - Workflow execution is intentionally blocked (no hidden fallback).
- `workflow_execution_mode=demo_fallback`
  - Explicit deterministic fallback bars are active.
  - This is acceptable for local/dev testing only.

## 3) Operator click-path verification (Phase 1 gate)

### A. Analysis (`/analysis`)

Verify:
- symbol, strategy, timeframe selectors work.
- **Refresh analysis** loads setup + chart.
- workflow source badge is visible.
- create-recommendation CTA is enabled for equities mode.

### B. Recommendations (`/recommendations`)

Verify:
- queue loads deterministically.
- selected recommendation detail shows symbol/strategy/timeframe/source.
- source label is explicit (`provider` or `fallback (...)`).
- replay/order CTAs open with recommendation context query params.

### C. Replay (`/replay-runs`)

Verify:
- run completes and appears in run table.
- selected run shows source mode and recommendation relationship.
- steps panel remains usable even if a single steps fetch fails.

### D. Orders (`/orders`)

Verify:
- stage order produces paper order row.
- selected order preserves recommendation linkage and workflow source.
- blotter explicitly states paper/dev only.

### E. Provider Health (`/admin/provider-health`)

Verify:
- configured provider + effective read mode + workflow execution mode are visible.
- operational impact text matches current mode (`provider`, `demo_fallback`, `blocked`).
- dashboard provider summary matches provider-health truth values.

## 4) What is private-alpha quality vs production-ready

### Private-alpha ready (Phase 1 scope)

- invite-gated operator workflow
- deterministic analysis → recommendation → replay → paper-order path
- explicit provider/fallback truth and blocked-mode behavior
- identity reconciliation that preserves local approval/role authority

### Intentionally deferred (not production-ready)

- options/crypto execution workflows (research preview only)
- brokerage/live order integrations
- public-facing onboarding
- full E2E browser automation suite

## 5) Common local recovery playbook

### Stale frontend build/cache behavior

1. Stop backend + frontend.
2. Clear Next build cache: `rm -rf apps/web/.next`
3. Restart backend/frontend.

### Provider entitlement/health mismatch

- Confirm `.env` keys and entitlement.
- Check `/admin/provider-health` for failure reason.
- For local deterministic testing only, set:
  - `ENVIRONMENT=local`
  - `WORKFLOW_DEMO_FALLBACK=true`

### SQLite local gotchas

- Stop services before deleting the sqlite file.
- Re-run:
  - `python -m macmarket_trader.cli init-db`
  - `python -m macmarket_trader.cli seed-demo-data`

### Duplicate identity reconciliation

Use one-time local utility if old split identities exist:

```bash
python scripts/reconcile_duplicate_users.py
```

Then sign out/in and verify `/admin/users` contains one canonical row per user with preserved role/approval.

## 6) Phase 1 validation commands

```bash
pytest -q
cd apps/web && npm test && npm run build
```

Phase 1 should not be marked closed unless these checks pass and the click path above is operator-usable.
