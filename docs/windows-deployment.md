# Windows Private-Alpha Deployment

Canonical deployment scripts live in `scripts/`.

## Auth provider default for deployment

- Deployment/private-alpha runtime should use Clerk (`AUTH_PROVIDER=clerk`).
- Mock auth is local/test only and is blocked at startup for non-`dev/local/test` environments.

## Canonical scripts

- `scripts/deploy_windows.bat`
- `scripts/restart_windows.bat`
- `scripts/run_backend_dev_windows.bat`
- `scripts/run_frontend_dev_windows.bat`

Root-level batch files are thin wrappers only.

## Canonical directories

- Repository clone: `C:\Dashboard\MacMarket-Trader\repo`
- Live runtime: `C:\Dashboard\MacMarket-Trader\live`

## Ports

- Frontend: `9500`
- Backend API: `9510`

## Deploy flow (`scripts/deploy_windows.bat`)

1. Stop listeners on ports `9500`/`9510`.
2. Fetch/reset repo clone (`origin/main`).
3. Mirror repo into live directory while preserving runtime state.
4. Create/activate venv, install backend dependencies.
5. Initialize DB and run backend tests.
6. Install/build frontend if present.
7. Start backend and frontend processes with logs.

## Runtime state safety

Deploy mirror excludes runtime state from destructive replacement, including:
- `.env`
- `.auth/`
- `logs/`
- sqlite files (`*.sqlite`, `*.sqlite3`)
- data/storage/upload directories (`data`, `storage`, `uploads`)

The mirror also excludes local development/test noise so deploys do not copy
AI worktrees, pytest scratch folders, or generated TypeScript incremental
state into the runtime folder. Current Robocopy exclusions include `.auth/`,
`.claude/`, `.pytest-tmp/`, `.tmp/`, and `*.tsbuildinfo`.

`scripts/deploy_windows.bat` recreates an ignored runtime `.tmp/` folder after
mirroring and runs backend pytest with a deployment-local basetemp under
`.tmp/pytest-deploy`. This keeps deployment tests independent from stale source
scratch folders and from machine-wide pytest temp-directory permissions.

## Deployed browser smoke

Authenticated deployed UI smoke is optional release evidence for the
Cloudflare Access protected app. It should use a dedicated smoke user and local
secrets only. From the source checkout:

```powershell
cd apps\web
npm run smoke:deployed
```

Set `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` for the Cloudflare Access
service token and/or `SMOKE_AUTH_STORAGE_STATE` for a Playwright storage state.
The smoke is non-mutating by default and writes screenshots plus JSON/Markdown
evidence under `.tmp/evidence/deployed-ui-smoke-*/`. Do not copy `.auth/`
storage-state files into the deployment mirror.

## Fail-fast behavior

Critical commands are guarded with `|| goto :fail` and deployment stops immediately on failure.
