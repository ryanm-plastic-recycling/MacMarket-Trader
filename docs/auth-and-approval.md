# Auth and Approval Workflow

Frontend authentication is handled by Clerk; backend verifies bearer tokens using the configured auth provider boundary.

## Workflow

1. User signs up and verifies email in Clerk.
2. Backend verifies token, hydrates missing profile fields from Clerk Backend API when needed, and upserts local `app_users`.
3. New users remain `pending` until admin action.
4. Pending/rejected users are blocked from approved-product routes.
5. Admin reviews `/admin/users/pending` and approves/rejects through admin endpoints.
6. Approval/rejection sends transactional email via configured email provider and logs delivery.

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

## MFA policy

- Admin MFA required by config (`require_mfa_for_admin=true`).
- Non-admin MFA can be globally enforced later (`enforce_global_mfa`).

## Env variables relevant to auth sync

Repo root `.env` (backend):
- `AUTH_PROVIDER=mock|clerk`
- `CLERK_JWT_ISSUER`
- `CLERK_JWKS_URL`
- `CLERK_JWT_AUDIENCE` (optional)
- `CLERK_SECRET_KEY` (required for Clerk profile hydration fallback)
- `CLERK_API_BASE_URL` (defaults to `https://api.clerk.com`)

## Frontend access flows

- `/sign-in` and `/sign-up` use Clerk hosted UI components.
- Authenticated users with `pending` approval are redirected to `/pending-approval`.
- Authenticated users with rejected/suspended or insufficient-role access are redirected to `/access-denied`.
- Frontend hosted paths no longer fall back to mock bearer tokens.
