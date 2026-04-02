# AGENTS.md

## Repo charter

Read `README.md` first. Treat it as the canonical architecture charter.
Do not shrink the root README into a status page.
Do not remove or dilute the HACO/HACOLT policy.

## Product-priority rules

- HACO/HACOLT are important supporting modules, but they are not the center of the product.
- The flagship operator surface is the Recommendations workspace.
- Replay, Orders, Account, Admin, and Provider Health must feel like real operator tools, not placeholders.

## Product rules

- MacMarket-Trader is a research-first, event-driven trading system.
- LLMs extract/explain; deterministic rules decide and size.
- HACO/HACOLT are retained as charting/context/research components, not the sole approval engine.
- Security, approval gating, auditability, and deterministic risk are mandatory.
1. Product center
- Recommendations Workspace is the flagship product surface.
- HACO is supporting technical context, not the center of the product.

2. Workflow coherence
- If provider-backed market data is configured, user-facing recommendation/replay/order flows must prefer provider-backed bars over demo bars.
- Fallback mode must be explicit, never hidden.

3. Admin and account usefulness
- Admin surfaces must show current users, not only pending users/invites.
- Persist and display practical account metadata such as last_seen_at / last_authenticated_at when available.

4. Operator-console quality bar
- Avoid placeholder-only pages.
- Every primary page must answer: what is this for, what should the operator do next, and what data supports that action.

5. HACO scope discipline
- Preserve the dedicated HACO page and dashboard HACO module.
- Do not force HACO into unrelated workflows unless it materially supports the decision.

## Working style

- Prefer small, bounded changes.
- Run tests before finishing.
- For frontend changes, ensure `npm install` and `npm run build` succeed.
- For backend changes, run `pytest`.
- Keep docs aligned with implementation.

## UI and workflow rules

- Every core operator page must implement all four states:
  - loading
  - empty
  - error
  - populated
- Core console pages should not rely primarily on ad hoc inline styles.
- Favor reusable console components and a consistent operator-console design language.
- Do not expose raw backend/provider errors directly as the primary UX.
- Provide operator-actionable guidance when external providers fail.

## Charting correctness rules

- Any chart layer derived from the same bar series must share one canonical indexed time base.
- Price bars, signal markers, HACO strip, and HACOLT strip must remain aligned under zoom/pan.
- Do not ship unsynced visual indicator strips as the primary implementation.

## Productization rules

- Invite-only onboarding is the primary private-alpha path unless explicitly changed.
- Do not treat public self-signup as the main go-to-market flow.
- The app should be presentable in local/dev mode with deterministic seed data for core workflows.

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


## Productization guardrail addendum (2026-04)

- Recommendations workspace is the flagship operator workflow.
- HACO is supporting technical context, not the product center.
- Core operator pages must ship loading, empty, error, and populated states.
- Operator surfaces with shared signal bars must share canonical synced time scales.
- Avoid large inline-style-only implementations for core console pages.
