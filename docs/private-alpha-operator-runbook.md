# Private Alpha Operator Runbook (Phase 5/6)

Last updated: 2026-04-15

This runbook is for internal operators validating the **Phase 5/6 product center**:

1. Analysis / Strategy Workbench
2. Recommendations
3. Replay
4. Paper Orders (including close-trade lifecycle)
5. Strategy Schedules
6. Provider Health truth checks

## 1) Local start checklist

### Frontend runtime requirements

- Use **Node `20.19.6`** (matches `apps/web/package.json` engines).
- On Windows, run verification from a local non-OneDrive path (for example `C:\dev\MacMarket-Trader`), not a OneDrive-synced directory, to avoid `.next` readlink `EINVAL` failures during `next build` and Playwright webServer startup.

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

### Backend (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn macmarket_trader.api.main:app --reload --port 9510
```

### Frontend (Windows PowerShell)

```powershell
Set-Location apps/web
npm install
npm run dev
```

### Seed deterministic operator data (Windows PowerShell)

```powershell
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

## 3) Operator click-path verification (Phase 5/6 guided flow)

The canonical path is **Analysis → Recommendations → Replay → Paper Orders**.
All steps pass context forward via URL query params (`guided=1`, `symbol`, `strategy`, `recommendation`, `replay_run`, `order`).
The WorkflowBanner at the top of each page shows the active lineage as chips.

### A. Analysis (`/analysis`)

Verify:
- Symbol, strategy, timeframe selectors work.
- Strategy selector shows description and regime hint below the dropdown.
- **Refresh analysis** loads setup + chart.
- Workflow source badge is visible.
- Create-recommendation CTA is enabled for equities mode.
- Clicking "Create recommendation" navigates to Recommendations with full guided query.

### B. Recommendations (`/recommendations`)

Verify:
- Queue loads deterministically.
- In guided mode, queue collapses by default with a "View recommendation queue (N)" toggle.
- Selected recommendation detail shows symbol/strategy/timeframe/source.
- Source label is explicit (`provider` or `fallback (...)`).
- "Make active" and "Save as alternative" are distinct actions (not the same button).
- Replay CTA passes recommendation lineage query params forward.

### C. Replay (`/replay-runs`)

Verify:
- Run completes and appears in run table.
- Selected run shows source mode and recommendation relationship.
- Steps panel renders approved (green left border) / rejected (red left border) rows.
- Stageability warning block (`op-error`) appears when `has_stageable_candidate === false`.
- Steps panel remains usable even if a single steps fetch fails.
- "Go to Paper Order step" button is active after a run with a stageable candidate.

### D. Orders (`/orders`)

Verify:
- Stage order produces paper order row.
- Selected order preserves recommendation linkage and workflow source.
- Paper portfolio summary card shows: Open positions / Open notional / Realized P&L / Win rate.
- "Close position" button appears for open orders; inline price input → "Confirm close" → P&L displayed.
- After close, the order status changes to "closed" and P&L shows green/red.
- Blotter explicitly states paper/dev only.

### E. Strategy Schedules (`/schedules`)

Verify:
- Schedule table shows relative time for last run (e.g., "2 hours ago").
- Top candidate badge shows classification count.
- Run history column shows `N top · N watch · N no-trade` format.
- Top candidates panel includes "Analyze in guided mode →" action link per candidate.
- Empty state (no schedules) shows an operator-useful CTA, not a blank page.

### F. Provider Health (`/admin/provider-health`)

Verify:
- Configured provider + effective read mode + workflow execution mode are visible.
- Operational impact text matches current mode (`provider`, `demo_fallback`, `blocked`).
- Dashboard provider summary matches provider-health truth values.

## 4) What is private-alpha quality vs production-ready

### Private-alpha ready (Phase 5/6 scope)

- Invite-gated operator workflow with full Clerk + local DB approval loop
- Deterministic 4-step guided path: Analysis → Recommendations → Replay → Paper Orders
- Close-trade lifecycle: positions opened on stage, closed with explicit action, realized P&L recorded
- Strategy schedules: create/run/inspect with guided-mode action links on top candidates
- Explicit provider/fallback truth and blocked-mode behavior
- Identity reconciliation that preserves local approval/role authority
- Data isolation: all user data scoped to `app_user_id` — second operator sees only their own records
- 141 backend pytest tests + 48 Vitest frontend tests + 8 Playwright e2e tests passing

### Intentionally deferred (not production-ready)

- Options/crypto execution workflows (research preview only)
- Brokerage/live order integrations
- `atm_straddle_mid` expected-range method
- Public-facing onboarding
- Realized P&L persistence across page reload (currently in-session state only)

## 5) Common local recovery playbook

### Stale frontend build/cache behavior

1. Stop backend + frontend.
2. Clear Next build cache: `rm -rf apps/web/.next` (bash) or `Remove-Item -Recurse -Force apps/web/.next` (PowerShell).
3. If on Windows and the repo is in OneDrive, move it to a non-synced local path first (OneDrive file virtualization can break `.next` symlink/readlink behavior).
4. Restart backend/frontend.

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

```powershell
python scripts/reconcile_duplicate_users.py
```

Then sign out/in and verify `/admin/users` contains one canonical row per user with preserved role/approval.

## 6) Validation commands

```bash
pytest -q
cd apps/web && npx tsc --noEmit && npm test && npm run build
```

```powershell
pytest -q
Set-Location apps/web
npx tsc --noEmit
npm test
npm run build
```

If pytest picks up a non-test auth mode from a local `.env`, force test mode inline:

```bash
ENVIRONMENT=test AUTH_PROVIDER=mock pytest -q
```

Phase 5/6 private-alpha readiness requires: 141 pytest tests passing, clean TypeScript build, and the full guided click-path above completing without errors for at least one operator.

## 7) User persistence and DB safety

### DB is never overwritten by a deploy run

`scripts/deploy_windows.bat` runs robocopy with `/XF "*.sqlite" "*.sqlite3" "*.db"`.
`macmarket_trader.db` at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db` is **never touched by a deploy run**.
All user rows, approval state, recommendation records, and replay history survive redeployment intact.

### If the DB is ever lost: manual admin re-seeding procedure

If `macmarket_trader.db` is deleted or corrupted, recreate the schema first:

```bash
python -m macmarket_trader.cli init-db
```

```powershell
python -m macmarket_trader.cli init-db
```

Then insert a bootstrap admin row **before the first Clerk sign-in**. The `external_auth_user_id`
must match the `sub` claim from your Clerk JWT (see next section for how to find it).

```bash
python -c "
import sqlite3
conn = sqlite3.connect('C:/Dashboard/MacMarket-Trader/macmarket_trader.db')
conn.execute('''
    INSERT INTO app_users (
        external_auth_user_id,
        email,
        display_name,
        approval_status,
        app_role,
        mfa_enabled,
        created_at
    ) VALUES (
        'user_XXXXXXXXXXXXXXXXXX',
        'you@example.com',
        'Your Name',
        'approved',
        'admin',
        0,
        CURRENT_TIMESTAMP
    )
''')
conn.commit()
conn.close()
print('Admin row inserted.')
"
```

```powershell
python -c "
import sqlite3
conn = sqlite3.connect(r'C:\Dashboard\MacMarket-Trader\macmarket_trader.db')
conn.execute('''
    INSERT INTO app_users (
        external_auth_user_id,
        email,
        display_name,
        approval_status,
        app_role,
        mfa_enabled,
        created_at
    ) VALUES (
        'user_XXXXXXXXXXXXXXXXXX',
        'you@example.com',
        'Your Name',
        'approved',
        'admin',
        0,
        CURRENT_TIMESTAMP
    )
''')
conn.commit()
conn.close()
print('Admin row inserted.')
"
```

Sign in via Clerk after inserting the row. The first-login sync (`upsert_from_auth`) will match
on `external_auth_user_id`, preserve `approval_status=approved` and `app_role=admin`, and fill in
any identity fields from Clerk claims. Verify the result after sign-in:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('C:/Dashboard/MacMarket-Trader/macmarket_trader.db')
rows = conn.execute('SELECT id, email, approval_status, app_role FROM app_users').fetchall()
for r in rows: print(r)
conn.close()
"
```

### Clerk external_auth_user_id = JWT sub claim

The `external_auth_user_id` column in `app_users` is always the `sub` claim from the Clerk JWT.
This is the only stable identifier — email and display name can change.

To find your sub claim:
- **Clerk dashboard** → Users → select user → copy the **User ID** field (format: `user_XXXXXXXXXXXXXXXXXX`)
- **Or** decode any Clerk JWT: the middle base64 segment is the payload. Extract `sub` from it.

Do not use email as the lookup key. Only `sub` is guaranteed stable across Clerk identity changes.

### Warning: bootstrap_admin.py only works if users already exist in the DB

`bootstrap_admin.py` (repo root) runs `UPDATE app_users SET approval_status='approved', app_role='admin' WHERE id = ?`.

If the DB was just initialized and no user has signed in yet, the script will run without error
but will update **zero rows silently** — it has no INSERT path.

**Correct sequence:**
1. If DB is fresh: use the INSERT command above to seed the admin row first.
2. If the user has already signed in at least once (row exists): use `bootstrap_admin.py` to promote them.

Running `bootstrap_admin.py` on an empty DB looks successful but does nothing.

---

## 8) Clerk configuration requirements (environment, not code)

These settings must be configured in the **Clerk dashboard** before a second operator can sign up and be approved. They are environment config — not wired in code.

### Required Clerk dashboard settings

| Setting | Value | Where |
|---|---|---|
| Sign-up allowed | Enabled | Clerk dashboard → User & Authentication → Email, Phone, Username |
| Email address required | Yes | Same section |
| Sign-in identifiers | Email address | Same section |
| Redirect after sign-up | `/pending-approval` | Clerk dashboard → Paths → After sign-up |
| Redirect after sign-in | `/dashboard` | Clerk dashboard → Paths → After sign-in |
| JWT templates | None required (default Clerk JWT claims are sufficient) | — |

### Sign-up flow for a new operator

1. New operator navigates to `/sign-up` and creates a Clerk account.
2. After sign-up, they are redirected to `/pending-approval` (pending approval page).
3. Console layout gate checks `approval_status` from local DB. If `pending`, gate holds at `/pending-approval`.
4. Admin logs in, navigates to `/admin/pending-users`, and approves the new operator.
5. After approval, the operator can sign in and access the console without re-login (next page load checks the updated status).
6. Operator lands on `/dashboard` with the onboarding checklist and guided workflow CTA visible.

### If the `/admin/invites` page is configured

The invite send flow (if wired to an email provider) sends a Clerk invite link. To enable:
- Set `EMAIL_PROVIDER=resend` (or equivalent) and `EMAIL_FROM=...` in backend `.env`.
- Clerk invite links bypass the sign-up page and go directly to account creation.
- The approval flow is the same: new user starts as `pending` and must be approved.

---

## 9) Onboarding a second operator — checklist

Use this checklist when onboarding an additional operator to the private-alpha console.

### Pre-flight (admin)

- [ ] Backend `.env` has `ENVIRONMENT=local` (or `production`) and `AUTH_PROVIDER=clerk`
- [ ] Clerk dashboard has sign-up enabled (see section 8)
- [ ] Admin is signed in and can reach `/admin/pending-users`
- [ ] Deploy script has been run and the system is healthy (`pytest -q` clean, services up)

### Step 1 — Invite send (optional but recommended)

- [ ] Navigate to `/admin/invites` (if the invite flow is wired)
- [ ] Enter the new operator's email and send invite
- [ ] Confirm the invite email arrives (check `EMAIL_PROVIDER` setting)
- [ ] **OR** share the `/sign-up` URL directly with the operator

### Step 2 — New operator sign-up

- [ ] Operator navigates to `/sign-up` and creates a Clerk account
- [ ] After sign-up, operator is redirected to `/pending-approval`
- [ ] Operator sees "Your account is pending approval" copy (not a blank page)

### Step 3 — Admin approval

- [ ] Admin navigates to `/admin/pending-users`
- [ ] New operator row appears with Approve / Reject actions
- [ ] Admin clicks **Approve**
- [ ] Verify: `SELECT id, email, approval_status, app_role FROM app_users` shows `approved` for new user

### Step 4 — First login as new operator

- [ ] Operator refreshes or re-navigates — console layout clears the pending gate
- [ ] Operator lands on `/dashboard`
- [ ] Onboarding checklist is visible (all steps unchecked for a brand-new account)
- [ ] Guided workflow CTA ("Start guided workflow") is visible

### Step 5 — Guided workflow walkthrough

- [ ] Operator clicks guided workflow CTA → lands on `/analysis?guided=1`
- [ ] Operator selects a symbol + strategy, refreshes analysis, creates a recommendation
- [ ] Recommendation appears in queue at `/recommendations?guided=1&...`
- [ ] Operator promotes the recommendation and proceeds to Replay
- [ ] Replay run completes at `/replay-runs?guided=1&...` with stageable candidate
- [ ] Operator stages a paper order at `/orders?guided=1&...`
- [ ] Paper order row appears in order history; portfolio summary card updates

### Step 6 — Data isolation confirmation

Run these SQL queries on the deployed DB to confirm the new operator's data is scoped:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('C:/Dashboard/MacMarket-Trader/macmarket_trader.db')
# Confirm user IDs
rows = conn.execute('SELECT id, email, approval_status FROM app_users').fetchall()
for r in rows: print(r)
# Confirm recommendations scoped to new operator's ID (replace N with their id)
# rows = conn.execute('SELECT id, app_user_id FROM recommendations WHERE app_user_id = N').fetchall()
# Confirm replay runs scoped
# rows = conn.execute('SELECT id, app_user_id FROM replay_runs WHERE app_user_id = N').fetchall()
conn.close()
"
```

All 7 user-scoped entities (recommendations, replay runs, orders, paper positions, paper trades, onboarding status, strategy schedules) are verified to filter by `app_user_id` in code — no cross-operator data leakage is possible.

---

## 10) Scheduled report runner (Windows Task Scheduler)

Strategy schedules are triggered by `python -m macmarket_trader.cli run-due-strategy-schedules`.
On Windows deployments, this should be run on a recurring schedule via Task Scheduler.

### Register the task

Run once from an elevated (Administrator) command prompt:

```bat
schtasks /create /tn "MacMarket-StrategyScheduler" ^
  /tr "C:\Dashboard\MacMarket-Trader\.venv\Scripts\python.exe -m macmarket_trader.cli run-due-strategy-schedules" ^
  /sc minute /mo 15 /st 00:00 /ru SYSTEM /f
```

This registers a task named `MacMarket-StrategyScheduler` that runs every 15 minutes as SYSTEM.
The `/f` flag overwrites any previously registered task with the same name.

### Verify it registered

```bat
schtasks /query /tn "MacMarket-StrategyScheduler"
```

Expected output includes `Status: Ready` and the trigger interval.

### Check last run time

```bat
schtasks /query /tn "MacMarket-StrategyScheduler" /fo LIST /v
```

Look for `Last Run Time` and `Last Result` in the output.
`Last Result: 0` means the last execution completed successfully.

### Remove the task if needed

```bat
schtasks /delete /tn "MacMarket-StrategyScheduler" /f
```

The `/f` flag suppresses the confirmation prompt.
