# MacMarket-Trader: Complete Claude Code & Development Guide

> Written specifically for your repo, your folder structure, and your workflow.
> Think of this as your "ChatGPT system prompt" but for Claude Code.

---

## PART 1 — WHAT YOUR REPO IS (Quick Summary)

Your project is a **research-first, event-driven trading intelligence console** with:

| Layer | Tech | Location |
|---|---|---|
| Backend API | Python + FastAPI + SQLite | `src/macmarket_trader/` |
| Frontend | Next.js (TypeScript) | `apps/web/` |
| Auth | Clerk (external) + local DB approval | Both layers |
| Database migrations | Alembic | `alembic/` |
| Tests (backend) | pytest (78 tests) | `tests/` |
| Tests (frontend) | Vitest (59 tests) | `apps/web/` |
| E2E tests | Playwright | `apps/web/tests/e2e/` |

**Your two paths:**
- **Dev/edit path:** `C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader`
- **Running/deployed path:** `C:\Dashboard\MacMarket-Trader`
- **Deploy bridge:** Run `deploy-macmarket-trader.bat` to copy dev → deployed + start servers

**Current phase status:**
- ✅ Phase 0 (scaffold) — DONE
- ✅ Phase 1 (domain model + hardening) — FUNCTIONALLY COMPLETE (78 backend tests pass)
- ✅ Phase 2 (alpha differentiators: Symbol Analyze, ranked queue, scheduled reports) — COMPLETE
- 🔄 Phase 3 (paid beta) — IN PROGRESS
- ⬜ Phase 4 (vendor integrations: Polygon, real brokers)
- ⬜ Phase 5 (full operator console polish)

---

## PART 2 — SETTING UP CLAUDE CODE (Step by Step)

Claude Code is like ChatGPT/Codex but it runs IN your terminal with full access to your files. It can read every file, run tests, edit code, and tell you what broke.

### Step 1: Open Claude Code in your repo

Open **Windows Terminal** or **PowerShell** and run:

```powershell
cd "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader"
claude
```

You'll see a prompt like `>`. You're now inside Claude Code talking about YOUR repo.

### Step 2: Give Claude Code context on your first session

Paste this as your FIRST message every time you start a new Claude Code session:

```
I'm working on MacMarket-Trader. Please:
1. Read README.md (architecture charter)
2. Read docs/roadmap-status.md (current phase status)
3. Read docs/local-development.md (how to run it)

Then summarize what phase we're in and what the current open work is.
```

This gives Claude Code the full context it needs — just like giving ChatGPT a system prompt.

### Step 3: Understand what Claude Code CAN do for you

Claude Code can:
- Read ALL your files at once (it has full repo access)
- Run `pytest`, `npm test`, `npm run build` in your terminal
- Edit files directly (you'll see diffs and approve them)
- Suggest code changes across multiple files at once
- Run your deploy script and tell you if it fails

Claude Code CANNOT:
- Push to GitHub for you (you still use GitHub Desktop)
- Access external services (Polygon, Clerk dashboard, etc.)
- See your `.env` secrets unless you paste relevant parts

---

## PART 3 — DEPLOYING & TESTING CURRENT STATE (Step by Step)

### Step 1: Make sure your .env files exist

Before deploying, your deployed folder needs environment files. Check if they exist:

```powershell
# Check if deployed .env exists
Test-Path "C:\Dashboard\MacMarket-Trader\.env"

# Check if deployed frontend .env.local exists  
Test-Path "C:\Dashboard\MacMarket-Trader\apps\web\.env.local"
```

If they DON'T exist, you need to create them once:

```powershell
# Copy the example files to the deployment folder (first time only)
Copy-Item "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader\.env.example" `
          "C:\Dashboard\MacMarket-Trader\.env"

Copy-Item "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader\apps\web\.env.local.example" `
          "C:\Dashboard\MacMarket-Trader\apps\web\.env.local"
```

Then open those files and set the minimum required values for local/dev mode:

**`C:\Dashboard\MacMarket-Trader\.env` (minimum for local testing):**
```
ENVIRONMENT=local
AUTH_PROVIDER=mock
EMAIL_PROVIDER=console
WORKFLOW_DEMO_FALLBACK=true
POLYGON_ENABLED=false
MARKET_DATA_PROVIDER=fallback
MARKET_DATA_ENABLED=false
```

**`C:\Dashboard\MacMarket-Trader\apps\web\.env.local` (minimum for local testing):**
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...   ← your Clerk key
CLERK_SECRET_KEY=sk_test_...                     ← your Clerk secret
BACKEND_API_ORIGIN=http://127.0.0.1:9510
```

> ⚠️ Note: If you're using `AUTH_PROVIDER=mock` (no real Clerk), you don't need real Clerk keys. 
> Check your existing `.env` in the dev folder for what you already have.

### Step 2: Run the deploy script

Right-click `deploy-macmarket-trader.bat` in your dev folder and **Run as Administrator**, OR in an elevated terminal:

```powershell
cd "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader"
.\deploy-macmarket-trader.bat
```

**What this script does automatically:**
1. Stops any running servers on ports 9510 (backend) and 9500 (frontend)
2. Copies (mirrors) your dev folder → `C:\Dashboard\MacMarket-Trader` (skips `.env`, `.git`, `node_modules`, DB files)
3. Creates a Python 3.13 virtual environment in the deployed folder
4. Runs `pip install -e ".[dev]"` to install Python dependencies
5. Initializes the SQLite database
6. Runs `pytest -q` (78 backend tests)
7. Runs `npm ci` + `npm run build` + `npm test` for the frontend
8. Starts the backend on port 9510 and frontend on port 9500
9. Waits for health checks to pass

**Expected success output:**
```
[OK] Deployment completed successfully.
```

**If it fails**, the script will show you exactly which step failed. Common fixes:

| Error | Fix |
|---|---|
| `Python 3.13 venv failed` | Install Python 3.13 from python.org |
| `Backend tests failed` | Run `pytest -q` manually in the deployed folder to see which tests fail |
| `Frontend build failed` | Check Node version is v20.x with `node -v` |
| `Backend health check failed` | Check `C:\Dashboard\MacMarket-Trader\logs\backend.log` |

### Step 3: Verify it's running

Open your browser to:
- **Frontend:** http://localhost:9500
- **Backend health:** http://localhost:9510/health  ← should return `{"status":"ok",...}`

### Step 4: Seed demo data (so the UI isn't empty)

In PowerShell (with the deployed venv active):

```powershell
cd "C:\Dashboard\MacMarket-Trader"
.\.venv\Scripts\activate
python -m macmarket_trader.cli seed-demo-data
```

### Step 5: Test the operator workflow manually

Follow this click path to verify everything works end-to-end:

1. Go to http://localhost:9500 and sign in
2. `/analysis` → pick a symbol (e.g. NVDA), pick a timeframe, pick a strategy → click **Refresh Analysis**
3. Click **Create recommendation from this setup**
4. `/recommendations` → review the recommendation detail pane
5. Click to open a replay run
6. `/replay-runs` → run the replay, verify steps appear
7. `/orders` → verify paper order staging works
8. http://localhost:9510/admin/provider-health → verify provider truth shows (fallback mode expected)

---

## PART 4 — HOW TO USE CLAUDE CODE FOR EACH PHASE

### The golden rule: One phase at a time on its own branch

```powershell
# In your dev folder (GitHub Desktop folder)
# BEFORE starting any new phase, create a branch:
git checkout -b phase-2-alpha-differentiators
```

Then work in Claude Code. When done and tested, merge back to main via GitHub Desktop.

### Starting a Claude Code session for a phase

Open Terminal → navigate to dev folder → run `claude` → paste this opener:

```
Read README.md, docs/roadmap-status.md, and docs/local-development.md first.

We're working on [PHASE NAME]. Here's what the roadmap says about it:
[paste the relevant section from docs/roadmap-status.md]

The current open items are:
[list the specific things you want done]

Please start by reviewing the existing code in [relevant folder] and tell me 
what already exists before writing anything new.
```

### Phase-specific openers to use with Claude Code

**For Phase 2 remaining gaps (you're here now):**
```
Read README.md and docs/roadmap-status.md.

We're finishing Phase 2 alpha differentiators. The roadmap says these are still open:
- Recommendations page needs persisted recommendation + ranked queue side-by-side lineage UX polish
- Analyze triage can be improved with richer indicator scenario provenance and strategy-specific explainability text
- Schedules page needs finer-grained editing controls (frequency/timezone/email target) and per-run detail drill-in
- Admin invite/onboarding surfaces need stronger "recent activity + next action" operational guidance polish
- Additional frontend unit coverage for new client-side queue/schedule state helpers

Start by looking at the current state of apps/web/components and apps/web/app/(console)/
and tell me which of these gaps are highest impact to tackle first.
```

**For Phase 3 (paid beta):**
```
Read README.md and docs/roadmap-status.md.

We're starting Phase 3 - paid beta. Requirements per roadmap:
- multiple user watchlists
- per-user schedules  
- email delivery + report history
- stronger provider support
- better replay visualization
- stronger ranking model
- onboarding and account quality
- operational logs and audit trail

Before writing anything, review the existing watchlists/schedules/email code in:
- src/macmarket_trader/ (backend)
- apps/web/app/(console)/schedules/ (frontend)
- apps/web/app/api/user/watchlists/

Tell me what already exists and what needs to be built new.
```

**For Phase 4 (vendor integrations):**
```
Read README.md, docs/market-data.md, and docs/provider-architecture.md.

We're doing Phase 4 - replacing mock providers with real ones.
The goal is to wire up Polygon.io for market data while keeping the same interfaces.

Review:
- src/macmarket_trader/data/providers/base.py (the interface)
- src/macmarket_trader/data/providers/mock.py (what we're replacing)
- src/macmarket_trader/data/providers/market_data.py (current Polygon scaffold)

Tell me what's already been scaffolded vs what needs to be built.
```

---

## PART 5 — TESTING GATES (Don't skip these)

After Claude Code makes changes, ALWAYS run these before deploying:

### Backend tests
```powershell
cd "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader"
.\.venv\Scripts\activate   # if not already active
pytest -q
```
✅ Expected: all tests pass. If new code was added, you should see MORE tests passing than before.

### Frontend tests
```powershell
cd "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader\apps\web"
npm test
```
✅ Expected: all tests pass.

### Frontend build (catches TypeScript errors)
```powershell
cd "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader\apps\web"
npm run build
```
✅ Expected: build completes with no errors.

### After all three pass → deploy
```powershell
cd "C:\Users\ryanm\OneDrive\Documents\GitHub\MacMarket-Trader"
.\deploy-macmarket-trader.bat
```

### Phase gate checklist before moving to the next phase

Don't start the next phase until you can check ALL of these:

- [ ] `pytest -q` passes (no regressions)
- [ ] `npm test` passes
- [ ] `npm run build` passes (no TypeScript errors)
- [ ] Deploy script completes successfully
- [ ] Manual operator click-path works: Analysis → Recommendations → Replay → Orders
- [ ] http://localhost:9510/health returns 200
- [ ] Provider health page shows correct fallback/provider state
- [ ] The new phase features work as expected in the browser

---

## PART 6 — CLAUDE CODE TIPS FOR BEGINNERS

### How to ask Claude Code to do things (good prompts)

**Good — specific, with context:**
> "Look at `src/macmarket_trader/ranking_engine.py` and `apps/web/app/api/user/recommendations/queue/route.ts`. The frontend queue page isn't showing the `score` field from the backend. Find the disconnect and fix it. Show me the diff before applying."

**Bad — too vague:**
> "Fix the recommendations page"

**Good — asking for review first:**
> "Before making any changes, read all the files in `apps/web/app/(console)/schedules/` and tell me what the current schedule editing controls support and what's missing."

**Good — asking Claude Code to run tests:**
> "After making your changes, run `pytest -q` and `npm test` and show me the results before I approve anything."

### Key commands inside Claude Code

```
/help          - see all commands
/clear         - clear conversation context (start fresh)
/exit          - exit Claude Code
```

You can also just type naturally, like ChatGPT.

### When Claude Code makes a change

It will show you a **diff** (what changed). You can:
- Type `yes` or `approve` to accept
- Type `no` or explain what to change instead
- Ask it to show you what the file looks like after the change before committing

### Keeping Claude Code in scope

Because you have a complex repo, tell Claude Code to stay focused:

> "Only touch files related to the schedules feature. Don't change anything in the recommendations or replay modules unless I specifically ask."

---

## PART 7 — WINDOWS-SPECIFIC NOTES

### Run the deploy script as Administrator
Port management (killing old processes) works better with admin rights. Right-click → "Run as Administrator" or use an elevated PowerShell window.

### OneDrive warning
Your dev folder is inside OneDrive. For the `npm run build` step specifically, OneDrive can cause issues with file locking. If the frontend build fails weirdly, try:

```powershell
# Pause OneDrive sync before building
# Or better: do final builds from the deployed folder directly:
cd "C:\Dashboard\MacMarket-Trader\apps\web"
npm run build
```

### Your .env files are NEVER copied by the deploy script
This is intentional and correct. The script skips `.env` and `.env.local` during the Robocopy mirror step. Your secrets stay in the deployed folder and are never overwritten by accident.

### Restarting without a full redeploy
If you only need to restart the servers (no code change):

```powershell
cd "C:\Dashboard\MacMarket-Trader"
.\restart-macmarket-trader.bat
```

---

## PART 8 — QUICK REFERENCE CARD

| Task | Command |
|---|---|
| Start Claude Code | `cd dev-folder && claude` |
| Run backend tests | `pytest -q` |
| Run frontend tests | `npm test` (from apps/web) |
| Build frontend | `npm run build` (from apps/web) |
| Deploy everything | `.\deploy-macmarket-trader.bat` |
| Restart servers only | `.\restart-macmarket-trader.bat` |
| Seed demo data | `python -m macmarket_trader.cli seed-demo-data` |
| Init database | `python -m macmarket_trader.cli init-db` |
| Run scheduled reports | `python -m macmarket_trader.cli run-due-strategy-schedules` |
| Backend health check | http://localhost:9510/health |
| App URL | http://localhost:9500 |
| Backend port | 9510 |
| Frontend port | 9500 |

---

---

## PART 9 — FIRST-TIME SETUP AND KNOWN ISSUES

### After a fresh database: promote yourself to admin

After `init-db` and your first Clerk sign-in, your account is created as `pending` / `user`.
You must manually promote it to admin before the admin pages work.

**Step 1 — Find your DB file** (default location in the deployed folder):
```
C:\Dashboard\MacMarket-Trader\macmarket_trader.db
```

**Step 2 — Sign in once through the browser** so the auth-sync creates your `app_users` row.

**Step 3 — Promote your row** using PowerShell + Python (no sqlite3 CLI required on Windows):

```powershell
cd "C:\Dashboard\MacMarket-Trader"
.\.venv\Scripts\activate
python -c "
import sqlite3
conn = sqlite3.connect('macmarket_trader.db')
conn.execute(\"UPDATE app_users SET app_role='admin', approval_status='approved' WHERE email='your@email.com'\")
conn.commit()
print('Rows updated:', conn.total_changes)
conn.close()
"
```

Columns involved: `app_role` (values: `user` / `admin`) and `approval_status` (values: `pending` / `approved` / `rejected`).

> The deploy script never overwrites the DB, so this promotion survives all future deploys.

---

### EMAIL_PROVIDER=console — emails print to the backend terminal, not your inbox

When `EMAIL_PROVIDER=console` is set in `.env`, all outbound emails (invites, strategy reports) are printed as formatted blocks in the backend terminal window (`backend.log` in the deployed folder).

Look for lines starting with `[EMAIL CONSOLE]` in the backend output. The full invite link is logged there during the invite flow.

---

### Getting real email delivery (Resend)

To send actual emails instead of logging them:

1. Create an account at resend.com and get an API key.
2. In `.env` (deployed folder):
   ```
   EMAIL_PROVIDER=resend
   RESEND_API_KEY=re_...
   ```
3. Restart the backend. Strategy report emails and invites will now deliver to real inboxes.

> The console provider remains the default for local dev. Never set `RESEND_API_KEY` in the dev folder's `.env`.

---

### Clerk session token lifetime and JWT leeway

Clerk issues session tokens with a 60-second expiry window.
The backend is configured with a **120-second JWT leeway** to absorb clock skew between the Clerk CDN and the local backend without producing spurious 401 errors.

If you see repeated `401 / Invalid token` errors that clear on refresh, check:
- That the backend is running and healthy (`http://localhost:9510/health`)
- That your system clock is not significantly drifted from internet time
- That `CLERK_SECRET_KEY` is set correctly in `apps/web/.env.local`

---

### Deploy script preserves the database on every run

The `deploy-macmarket-trader.bat` script now guards the `init_db` step:

- **If `macmarket_trader.db` already exists** — `init_db` is skipped. Your data, users, and schedules are preserved.
- **If no DB file exists** — `init_db` runs to create a fresh schema.

You should never lose production/operator data from a routine redeploy. To intentionally reset the DB, stop the backend, delete `macmarket_trader.db` manually, then redeploy.

---

*Guide generated from full review of MacMarket-Trader repo (April 2026)*