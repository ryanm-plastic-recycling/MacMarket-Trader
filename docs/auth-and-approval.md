# Auth and Approval Workflow

Authentication is handled by Clerk in the frontend; backend trusts verified session tokens/JWT claims via auth provider middleware.

## Workflow

1. User signs up and verifies email in Clerk.
2. Backend syncs user into `app_users` with `pending` approval status.
3. Pending users can authenticate but cannot access approved product routes.
4. Admin reviews pending users in `/admin/users/pending`.
5. Admin approves/rejects via API endpoints.
6. Approval/rejection transactional email is sent through email adapter.
7. Approved users can access product routes.

## MFA policy

- Admin MFA required by config (`require_mfa_for_admin=true`).
- Non-admin MFA is available and global enforcement can be enabled later (`enforce_global_mfa`).
