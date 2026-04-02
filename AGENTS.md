# AGENTS.md

## Repo charter

Read `README.md` first. Treat it as the canonical architecture charter.
Do not shrink the root README into a status page.
Do not remove or dilute the HACO/HACOLT policy.

## Product rules

- MacMarket-Trader is a research-first, event-driven trading system.
- LLMs extract/explain; deterministic rules decide and size.
- HACO/HACOLT are retained as charting/context/research components, not the sole approval engine.
- Security, approval gating, auditability, and deterministic risk are mandatory.

## Working style

- Prefer small, bounded changes.
- Run tests before finishing.
- For frontend changes, ensure `npm install` and `npm run build` succeed.
- For backend changes, run `pytest`.
- Keep docs aligned with implementation.

## Guardrails

- Do not replace real auth with mock auth in production-facing paths.
- Do not point browser code to localhost for hosted deployments.
- Do not delete canonical architecture sections from the root README.
- Do not add cosmetic UI work ahead of operator workflow value.
1. Never replace the long-form README with a short scaffold summary.
2. Never overwrite local `approval_status` or `app_role` from external auth claims.
3. Keep Clerk sign-in/sign-up routes compatible with Clerk docs and middleware public-route requirements.
4. Preserve HACO as both:
   - a dedicated workspace
   - a dashboard-integrated module
5. Do not downgrade data-driven operator pages back into placeholders.
6. Keep dependency changes intentional and keep lockfiles committed.
7. Keep Windows dev path and live runtime path separate.

## Hard architecture protections (must keep)

- Never shrink/replace the root README with a short status stub.
- Never overwrite local `approval_status` or `app_role` from external auth claims.
- Clerk sign-in/sign-up routes and middleware public-route config must remain Clerk-compatible.
- Preserve HACO in two places: dedicated workspace and dashboard-integrated module.
- Do not downgrade data-driven operator pages back to placeholders.
- Keep dependency changes intentional and keep `package-lock.json` committed when changed.
