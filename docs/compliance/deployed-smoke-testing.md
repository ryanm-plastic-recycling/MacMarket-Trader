# Deployed Browser Smoke Testing

This document defines the safe authenticated browser-smoke path for
`https://macmarket.io`. It is evidence collection only. It must not weaken
Cloudflare Access, Clerk, admin approval, paper-only boundaries, or provider
guardrails.

## Goals

- Verify deployed operator pages render behind Cloudflare Access.
- Capture screenshots, console errors, failed requests, and a JSON/Markdown
  evidence summary.
- Confirm paper-only and no-routing language remains visible where relevant.
- Keep the default smoke non-mutating.

## Auth Approaches

Preferred path for automation:

1. Create a Cloudflare Access service token scoped only to `macmarket.io`.
2. Add the token to a Cloudflare Access policy using the `Service Auth` action.
3. Use a dedicated approved Clerk test user for the app session.
4. Store the test user's Playwright storage state in a local ignored path such
   as `.auth/macmarket-smoke.json`.

Cloudflare documents service tokens as a Client ID and Client Secret for
automated systems. Requests authenticate by sending:

```text
CF-Access-Client-Id: <client id>
CF-Access-Client-Secret: <client secret>
```

Reference: https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/

Alternative path:

- Use a Playwright storage state captured after signing in through both
  Cloudflare Access and Clerk as a dedicated test user. This avoids putting the
  service token in the browser context, but the storage state file is still
  sensitive and must stay local.

Service tokens bypass Cloudflare Access only. They do not replace Clerk or
MacMarket's local `approval_status` / `app_role` authorization. Admin pages
still require an approved admin test user.

## Local Secret Storage

Do not commit smoke credentials or storage state. Use local shell environment
variables or a machine-local secret manager:

```powershell
$env:SMOKE_BASE_URL = "https://macmarket.io"
$env:CF_ACCESS_CLIENT_ID = "<client id>"
$env:CF_ACCESS_CLIENT_SECRET = "<client secret>"
$env:SMOKE_AUTH_STORAGE_STATE = "C:\Users\ryanm\.macmarket\macmarket-smoke-storage.json"
$env:SMOKE_TEST_USER_EMAIL = "smoke-admin@example.com"
```

The repo ignores `.auth/` for optional local storage-state files, and release
archive/deployment checks exclude `.auth/` alongside `.env`, `.tmp`, logs, DBs,
and generated build artifacts.

## Capturing Storage State

Use a dedicated approved smoke user, not a personal account. A practical manual
capture flow is:

```powershell
cd apps\web
npx playwright codegen --save-storage ..\..\.auth\macmarket-smoke.json https://macmarket.io
```

In the browser that opens, complete Cloudflare Access and Clerk sign-in for the
smoke user, then close the codegen session. Keep the resulting storage state
local and rotate it when the test user or session policy changes.

## Running The Smoke

From `apps/web`:

```powershell
npm run smoke:deployed
```

Equivalent direct command:

```powershell
npx playwright test --config=playwright.deployed-smoke.config.ts
```

If neither Cloudflare service-token headers nor a storage state file are
configured, the smoke writes a skipped evidence report and exits without
failing the release.

## Output

The smoke writes:

- `.tmp/evidence/deployed-ui-smoke-<timestamp>/summary.json`
- `.tmp/evidence/deployed-ui-smoke-<timestamp>/summary.md`
- `.tmp/evidence/deployed-ui-smoke-<timestamp>/screenshots/*.png`

The summary records only redacted auth configuration state:

- Cloudflare service token: configured/missing
- storage state: configured/missing
- test user email: configured/missing

It never prints token values, cookies, API keys, or auth headers.

## Pages Covered

The deployed smoke visits:

- `/dashboard`
- `/charts/haco`
- `/analysis`
- `/recommendations`
- `/orders`
- `/settings`
- `/admin/provider-health`

It verifies page markers such as Provider Health, Index Context, Analysis,
Recommendations, Orders, and safety wording where relevant.

## Mutation Policy

Default:

```powershell
$env:SMOKE_ALLOW_MUTATION = "false"
```

The smoke does not create, save, close, settle, roll, adjust, or route anything
by default. Any future mutating smoke step must require:

```powershell
$env:SMOKE_ALLOW_MUTATION = "true"
```

and must be scoped to a dedicated smoke user with records that can be safely
reset.

## What This Does Not Test

- It does not bypass Cloudflare Access.
- It does not test personal credentials.
- It does not prove securities-law compliance.
- It does not perform live trading, broker routing, automated exits, automatic
  rolls, or automatic adjustments.
- It does not spam provider, OpenAI, or options endpoints.

## Evidence Review

Before release, review the smoke Markdown and screenshots for:

- Cloudflare or Clerk auth gates where app pages should render.
- Missing Index Context or Provider Health readiness.
- Console errors or failed requests.
- Missing paper-only / no-routing language.
- Any text implying live execution readiness.
