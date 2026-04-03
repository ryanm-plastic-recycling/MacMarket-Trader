# Auth and Approval Workflow

Frontend authentication is handled by Clerk; backend verifies bearer tokens using the configured auth provider boundary.

## Workflow

1. Admin sends a private-alpha invite from `/admin/pending-users`.
2. Invited user follows invite link to Clerk sign-up/sign-in.
3. Backend verifies token, hydrates missing profile fields from Clerk Backend API when needed, and upserts local `app_users`.
4. Invited/new users remain `pending` until admin action.
5. Pending/rejected users are blocked from approved-product routes.
6. Admin reviews `/admin/users/pending` and approves/rejects through admin endpoints.
7. Approval/rejection/invite sends transactional email via configured email provider and logs delivery.

Legacy/public signup can still exist as Clerk plumbing, but private-alpha invite flow is the operator default.

## Invite flow details

- Admin endpoint: `POST /admin/invites` (admin + MFA required).
- Invite sends a Clerk-compatible sign-up URL and creates/updates a local pending user row.
- Invite-preprovisioned rows use an `invited::<email>` external ID placeholder, then bind to real Clerk `sub` at first successful login.
- `EMAIL_PROVIDER=console` logs invite destination, template, subject, and full body for local QA.

## Identity sync safeguards

- Sync lookup order is:
  1. `external_auth_user_id` match
  2. fallback `email` match for invited pre-provisioned users
- Existing local `approval_status` / `app_role` are never overwritten by auth claims.
- Existing local admin users remain admin across re-login sync.
- Pending invited users remain pending until explicit admin approval.
- New-user provisioning without stable email is blocked (prevents blank/fragile user rows).

## Source of truth and sync rules (hard policy)

- Clerk handles **authentication/identity**, not authorization.
- Local DB (`app_users`) is authoritative for:
  - `approval_status`
  - `app_role`
  - approval history / operator privileges
- Existing approved/admin users are never downgraded from upstream auth claims.
- Auth sync only updates safe identity fields:
  - `email` (when present)
  - `display_name` (when present)
  - `mfa_enabled`
- New local user creation requires a stable email identifier; if claims are sparse, backend attempts Clerk Backend API hydration (`CLERK_SECRET_KEY`).
- If hydration fails:
  - existing local user role/approval state remains unchanged,
  - existing email/display name are not wiped,
  - new-user provisioning is blocked rather than creating a broken auth row.

## Route policy

- Public: `GET /health`
- Approved-user required:
  - `POST /recommendations/generate`
  - `POST /replay/run`
  - `GET /user/dashboard`
- Admin-only: all `/admin/*` routes
  - including `POST /admin/invites`

## MFA policy

- Admin MFA required by config (`require_mfa_for_admin=true`).
- Non-admin MFA can be globally enforced later (`enforce_global_mfa`).

## Env variables relevant to auth sync

Repo root `.env` (backend):
- `AUTH_PROVIDER=mock|clerk`
- `ENVIRONMENT=dev|local|test|prod|...`
- `CLERK_JWT_ISSUER`
- `CLERK_JWKS_URL`
- `CLERK_JWT_AUDIENCE` (optional)
- `CLERK_SECRET_KEY` (required for Clerk profile hydration fallback)
- `CLERK_API_BASE_URL` (defaults to `https://api.clerk.com`)

Fail-closed runtime guardrail:
- `AUTH_PROVIDER=mock` is only allowed when `ENVIRONMENT` is `dev`, `local`, or `test`.
- Any other environment (for example `prod`) fails startup.

## Frontend access flows

- `/sign-in` and `/sign-up` use Clerk hosted UI components.
- Authenticated users with `pending` approval are redirected to `/pending-approval`.
- Authenticated users with rejected/suspended or insufficient-role access are redirected to `/access-denied`.
- Frontend hosted paths no longer fall back to mock bearer tokens.

## Invite-first onboarding flow

1. Admin sends invite from **Admin / Invites**.
2. Invitee signs in via Clerk invite link.
3. Local account remains `pending` until admin approval.
4. App role and approval status remain local-authoritative and are never overwritten by external auth claims.

## Identity hygiene and approval sync notes

- Local DB remains the source of truth for `approval_status` and `app_role`.
- Placeholder template emails (for example `{{...}}`) are ignored for display and replaced on next valid identity sync.
- Account/Admin pages surface an explicit identity warning when profile hydration is incomplete.

## Client auth readiness behavior (2026-04 update)

- Protected same-origin operator fetches rely on server-side session auth resolution first (`auth()` from route handlers).
- Client bearer token paths are now fallback-only for special cases, not the default workflow mechanism.
- If a signed-in session is still initializing token resolution, workflow routes return an auth-initializing response and UI keeps an inline loading state (instead of stale intermittent 401 banners).
- UI pages clear stale auth/error banners immediately after first successful fetch and keep loading/success/error feedback inline with retry controls.

## Provider vs fallback truth policy in operator workflows

- Dashboard, strategy workbench, recommendations, replay runs, orders, and provider health must label workflow source consistently.
- If fallback bars are used, UI labels fallback explicitly in metadata and chart/source chips.
- Chart context for selected recommendation should not silently mix with conflicting source context.

## Strategy-first workflow (2026-04)

1. Start at **Analysis / Strategy Workbench** (`/analysis`) to choose symbol, timeframe, and strategy.
2. Inspect chart context, trigger, entry/stop/targets, confidence filters, and source label.
3. Create recommendation from setup and jump to **Recommendations** for review/execution.
4. Move to **Replay** for deterministic validation and then **Orders** for paper staging.

## Account/admin operator usability notes

- Admin users view presents current users with role, approval state, MFA, invite state, and last seen/last authenticated metadata.
- Account page surfaces local role/approval truth, MFA state, sign-out action, and persisted theme preference.

## Authorization source-of-truth reminder

Scheduled report ownership is tied to local `app_users.id`. Local DB `approval_status` and `app_role` remain authoritative and are not overwritten from external auth claims.
