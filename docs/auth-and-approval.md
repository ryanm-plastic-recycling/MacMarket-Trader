# Auth and Approval Workflow

Frontend authentication is handled by Clerk; backend verifies bearer tokens using the configured auth provider boundary.

## Workflow

1. User signs up and verifies email in Clerk.
2. Backend verifies token, upserts local `app_users`, and persists role/MFA claims used for app policy checks.
3. New users remain `pending` until admin action.
4. Pending/rejected users are blocked from approved-product routes.
5. Admin reviews `/admin/users/pending` and approves/rejects through admin endpoints.
6. Approval/rejection sends transactional email via configured email provider and logs delivery.

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
