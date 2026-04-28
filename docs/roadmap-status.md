# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-04-28

## Positioning
MacMarket-Trader should not try to be “another brokerage chart page.”
It should be positioned as an invite-only, operator-grade trading intelligence console.

The defensible edge is not “we have AI.”
The defensible edge is:
- strategy-aware analysis
- event + regime context
- explicit trade levels
- replay before paper execution
- recurring ranked trade reports
- explainable AI layered on top of deterministic logic

## Current Status
MacMarket-Trader has completed **Phases 1–6** and post-launch polish. **Phase 5 is fully closed** (last gaps — strategy regime hints + role-conditional sidebar — landed this pass). **Phase 6 close-trade lifecycle is e2e-gated** end-to-end (open-positions list, inline close ticket, closed-trades blotter, lineage extension).
The system is verified: 173 backend tests passing, TypeScript clean, 74 vitest unit tests, **26 Playwright e2e** (all passing, no skips).

### 2026-04-28 Pass 4 — email logo real fix + cancel staged + reopen closed trade + scheduler audit

Three tracks. Test counts: backend **173 → 189** (+16: 7 email + 9 cancel/reopen). Frontend vitest **88 → 97** (+9 reopen helper tests). Playwright **27 → 31** (+4 cancel/reopen).

#### Track A — Email logo broken-image: real diagnosis and fix

**Pass 2 was wrong.** The "env-URL → base64 → CSS chain fallback" claim referred to dead code: production has `BRAND_LOGO_URL` set, so the very first branch always wins and `_logo_img()` emits `<img src="https://...">`. The base64 fallback was never reached.

**Root cause** (mix of spec causes (a) and (d)): Gmail renders `<img>` tags by proxying the URL through `googleusercontent.com`. The proxy fetches the URL **server-side**. If that fetch fails for any reason — DNS, cert, timeout, rate limit, anti-abuse rule, host quirk — Gmail shows a broken-image icon even when the URL loads fine in a browser. `logos.macmarket.io` (a subdomain not under our Cloudflare tunnel) was the unreliable hop.

**Resend send call** uses `payload = {from, to, subject, text, html}` only — **no `attachments` array**. So CID image embedding was never an option for the current adapter; the `<img>` tag's `src` attribute is the only thing that controls the rendered image.

**Fix** (`src/macmarket_trader/email_templates.py`): swap the priority order so the embedded base64 data URI is the **primary** path, with `BRAND_LOGO_URL` demoted to a deeper fallback only used if the on-disk PNG is missing. Inlined data URIs render reliably in Gmail / Outlook / Apple Mail because they don't depend on any proxy fetch. Cost: ~10 KB of email size (the lockup PNG is 33 KB → ~45 KB base64, but it caches client-side per Resend message).

**Test gate** (`tests/test_email_templates.py`, 7 new tests): asserts that even when `BRAND_LOGO_URL` is set, the rendered HTML for `_logo_img()`, `render_invite_html`, `render_approval_html`, and `render_rejection_html` contains `src="data:image/png;base64,..."` — and **does not** contain `logos.macmarket.io`. Two negative-path tests cover the deep-fallback chain (env URL kicks in only when the data URI is missing; CSS lockup kicks in when both are missing).

#### Track B — Cancel staged order + reopen closed position with 5-min window

**Backend (`api/routes/admin.py`, `storage/repositories.py`, `domain/models.py`):**
- New `OrderModel.canceled_at: datetime | null` column. Auto-applied on next startup by `apply_schema_updates` — no migration file needed.
- `OrderRepository` gains `has_fills(order_id)` and `cancel(order_id, *, canceled_at)`.
- `PaperPortfolioRepository` gains `get_trade_by_id(trade_id)`, `reopen_position(position_id, qty)` (sets `status='open'`, `closed_at=None`, restores `remaining_qty`), and `delete_trade(trade_id)` (hard delete, since reopen is an undo not a soft-delete).
- New endpoint `POST /user/orders/{order_id}/cancel` — 404 for non-owner, 409 if status ≠ "staged" or any fills exist, sets `status='canceled'` + `canceled_at`, writes audit log entry `{event: "order_canceled", order_id, recommendation_id, replay_run_id, app_user_id, canceled_at}`.
- New endpoint `POST /user/paper-trades/{trade_id}/reopen` — 404 for non-owner, 409 if `now - closed_at > REOPEN_WINDOW_SECONDS (5 min)`, 409 if parent position is not closed. Restores parent position, hard-deletes the trade row, writes audit log entry `{event: "position_reopened", position_id, trade_id, original_closed_at, original_realized_pnl, app_user_id, reopened_at}`. Audit captures the original PnL so the action is reversible by replay if ever needed.
- `_record_audit_event(*, recommendation_id, payload)` helper added for both paths — writes to the existing `audit_logs` table that `RecommendationRepository.create()` already uses; the `payload.event` field distinguishes the new lifecycle entries from the recommendation snapshots.
- `OrderRepository.list_with_fills` now serializes `canceled_at` so the orders blotter UI can show the cancellation timestamp.

**Backend tests** (`tests/test_close_trade_lifecycle.py`, 9 new): cancel happy path + audit row, cancel 409 fills, cancel 409 non-staged, cancel 404 non-owner, reopen happy path + audit row + trade row deletion, reopen 409 outside window (backdates `closed_at` 6 min in the past via direct DB write), reopen 409 already-open, reopen 404 non-owner, reopen invariant test (post-condition: position status=open, closed_at=None, remaining_qty restored, trade row hard-deleted).

**Next.js proxies:**
- `apps/web/app/api/user/orders/[orderId]/cancel/route.ts` (POST → backend)
- `apps/web/app/api/user/paper-trades/[tradeId]/reopen/route.ts` (POST → backend)

**Helpers** (`apps/web/lib/orders-helpers.ts`):
- `REOPEN_WINDOW_SECONDS = 5 * 60`.
- `reopenSecondsRemaining(closedAt, nowMs)` — clamps to 0 when expired or unparseable; returns `REOPEN_WINDOW_SECONDS` for future-dated input (clock-skew safety).
- `canReopenTrade(closedAt, nowMs)` — boolean predicate used by the UI to gate button visibility.
- 9 new vitest tests cover happy path, edge of window, expired, future-dated, and missing/invalid inputs.

**UI** (`apps/web/app/(console)/orders/page.tsx`):
- Order history table grew an action column. Rows where `status === "staged" && fills.length === 0` show a destructive **Cancel order** button. Click → inline confirm row ("Are you sure? This cannot be undone." + Yes/No), no modal — matches the existing close-ticket pattern. Confirm → POST cancel → refetch orders + positions → success feedback.
- Closed trades table grew an action column. Rows where `canReopenTrade(closed_at)` show a secondary **Reopen position** button with adjacent muted text `(undo within Xs)` showing live countdown. Click → inline confirm. Confirm → POST reopen → refetch positions + trades + portfolio summary → success feedback.
- 30-second `setInterval` updates a `nowMs` state value so the countdown decreases visibly and rows automatically lose the Reopen button after the 5-minute window closes (no manual refresh needed).

**Playwright e2e** (`apps/web/tests/e2e/phase6-cancel-reopen.spec.ts`, 4 new):
1. Cancel button is visible when order is staged with no fills.
2. Cancel button is NOT visible when order has fills.
3. Reopen button is visible (with countdown text) on a closed trade with `closed_at` 60 s ago.
4. Reopen button is NOT visible (and no countdown text) when `closed_at` is 10 minutes ago.

#### Track C — Operator action: audit Windows Task Scheduler

**Documented finding** (operator confirmed both tasks exist in Windows Task Scheduler):
- `MacMarket-StrategyScheduler` — created in Pass 2 by operator following runbook §12. Runs `scripts/run-due-schedules.ps1` (PowerShell) every 5 minutes; logs append to `logs/scheduler.log`. The script invokes `python -m macmarket_trader.cli run-due-strategy-schedules`.
- `MacMarket-Strategy-Reports` — pre-existing, registered by `scripts/setup_task_scheduler.bat`. Looking at the batch file, it runs the **same CLI command** (`python -m macmarket_trader.cli run-due-strategy-schedules`) but on a weekly schedule (Mon-Fri at 08:30) as SYSTEM with HIGHEST privileges.

**Risk to flag**: if both tasks are enabled, the strategy scheduler runs both at 08:30 each weekday morning *and* every 5 minutes via the Pass 2 task. The 08:30 weekday run is a no-op (the 5-min runner already covered it 5 min earlier), but if either task's working directory is misconfigured the duplicate invocation can produce two divergent scheduler.log streams. **Operator action required**: in Windows Task Scheduler, open Properties → Actions tab on each task and confirm what each one calls. If both call `run-due-strategy-schedules`, disable `MacMarket-Strategy-Reports` (the older one) and keep `MacMarket-StrategyScheduler` (the Pass 2 PowerShell-runner version with logging). Claude has no Task Scheduler visibility — this audit must be done at the deployment host.

#### Verification

- `pytest -q` — **189 passed** (was 173, +16: 7 email + 9 cancel/reopen).
- `npx tsc --noEmit` clean.
- `npm test` — **97 passed** (was 88, +9 reopen helper tests).
- `npx playwright test --reporter=list` — **31 passed**, 0 skipped (was 27, +4 cancel/reopen).

#### "Still open" items closed by this pass

- *Cancel staged order* — closed. Backend endpoint + audit log + UI affordance + 4 e2e tests gating visibility.
- *Reopen closed position* — closed. Backend endpoint with 5-min window + audit log + UI countdown + helper tests + e2e tests.

#### "Still open" items kept open

- **Display-friendly recommendation ID** — alongside canonical `rec_<hex>`, surface a human-meaningful slug like `AAPL-EVCONT-20260428-1430`. Requires schema migration on the recommendations table; deferred.
- **Per-user `risk_dollars_per_trade` configuration** — currently env-only via `RISK_DOLLARS_PER_TRADE`. Should be settable per operator from a Settings page. Requires `app_users` column + admin/account UI; deferred.

#### "Still open" items added by this pass

- **Operator-action item — Audit `MacMarket-Strategy-Reports` task** — verify what command it actually runs from the Task Scheduler GUI; if it's the same CLI as `MacMarket-StrategyScheduler`, disable the older task to avoid duplicate scheduler.log streams. Track C above explains the procedure. Claude cannot inspect Task Scheduler directly.

### 2026-04-28 Operational fixes — email logo relocation, scheduler runner, MFA rollout doc

Documentation-heavy pass with three operational fixes. Backend test count unchanged (173); frontend test counts unchanged (88 vitest, 27 Playwright).

**Section 1 — Email logo asset relocation (`config.py` + `.env.example`)**
- Brand asset audit of `apps/web/public/brand/`: confirmed PNG lockups exist as `square_console_ticks_lockup_light.png` (33.6 KB, transparent — works on the dark `#0f1923` email card) and `square_console_ticks_lockup_dark.png` (35.3 KB). Same filenames the base64 fallback in `email_templates.py::_load_logo_base64` already reads at process start.
- New default URL: `https://macmarket.io/brand/square_console_ticks_lockup_light.png`. Self-hosted via the Next.js `public/` static path so the email image and the in-app logo come from the same artifact — no separate logo CDN dependency.
- `Settings.brand_logo_url` default in `config.py` updated to the new URL with an inline comment explaining that the base64 embed remains as the deeper fallback.
- `.env.example` updated to the same default with a more accurate comment block (was previously implying the GitHub raw URL was canonical).
- **Email template logic was deliberately not changed.** The existing `_logo_img()` chain (env URL → base64 → CSS lockup) already produces a working image in every code path; "as a fallback if needed" was satisfied by leaving the in-process base64 as the deep fallback rather than introducing a hardcoded URL retry.
- **Operator action required** (manual, do not commit): on the deployment host, edit `C:\Dashboard\MacMarket-Trader\.env` and set `BRAND_LOGO_URL=https://macmarket.io/brand/square_console_ticks_lockup_light.png`. Restart the backend so the new env value is picked up. No backend code change is needed — `_logo_img()` reads `os.environ` directly each render.

**Section 2 — Strategy scheduler runner script (`scripts/run-due-schedules.ps1` + runbook §12)**
- New PowerShell runner wraps the existing CLI command. Sets `$ErrorActionPreference = "Stop"`, ensures `C:\Dashboard\MacMarket-Trader\logs\` exists (creates it if not), appends a `[yyyy-MM-dd HH:mm:ss] running due strategy schedules` line to `logs\scheduler.log`, then runs `.venv\Scripts\python.exe -m macmarket_trader.cli run-due-strategy-schedules` with stdout+stderr piped via `Add-Content` into the same log. `Push-Location`/`Pop-Location` keeps the working directory predictable.
- New runbook section `## 12) Strategy scheduler task registration` (after the existing schtasks-based §10 — both methods coexist, the new one is the recommended path because the GUI Task Scheduler exposes "missed start" recovery and per-failure retry that bare `schtasks` cannot express).
- Section 12 walks the operator through the **Create Task** GUI: General tab name + "Run whether user is logged on" + "Run with highest privileges"; Triggers daily 06:00 with 5-minute repeat for 1 day; Action `powershell.exe` with `-NoProfile -ExecutionPolicy Bypass -File C:\Dashboard\MacMarket-Trader\scripts\run-due-schedules.ps1`; Settings tab "Run task as soon as possible after a scheduled start is missed" + "Restart every 1 minute up to 3 times". Includes verify (`schtasks /query /tn "MacMarket-StrategyScheduler" /fo LIST /v`), sanity-check (manual invoke), and tail-the-log commands.
- `scripts/deploy_windows.bat` already greps for `MacMarket-StrategyScheduler` after every deploy and prints `[WARN]` when the task is missing — once registered per §12, that warning silences automatically.

**Section 3 — MFA pre-flight documentation (runbook §13)**
- New runbook section `## 13) MFA rollout sequence` covering the documented order: pre-flight checklist → Stage A (admins only, `REQUIRE_MFA_FOR_ADMIN=true`) → Stage B (all users, `ENFORCE_GLOBAL_MFA=true`).
- Pre-flight checklist enumerates: TOTP backup codes saved offline, at least one admin verified to log in with MFA on the **production tunnel domain** (not just localhost), Clerk recovery email current and verified.
- Stage A walks through the env flip, backend restart, login test, and the 1–2 day soak before progressing.
- Stage B mirrors Stage A for `ENFORCE_GLOBAL_MFA`.
- Recovery section calls out the two escape hatches: Clerk dashboard MFA disable for individual accounts, plus the `cloudflareaccess.com` outermost layer that lets admins reach the Clerk dashboard even if the application is unreachable.
- `.env` was **not** modified. Backend MFA enforcement code was **not** modified. The flags remain `false` everywhere they currently are; the section is the documented prerequisite an operator must complete before flipping them.

**Verification**
- `pytest -q` — **173 passed** (unchanged; backend untouched).
- `npx tsc --noEmit` clean.
- `npm test` — **88 passed** (16 files, unchanged).
- `npx playwright test --reporter=list` — **27 passed**, 0 skipped (unchanged).

**"Still open" items closed by this pass**
- *Strategy scheduler not running on schedule* — closed. The runner script + GUI-based registration in runbook §12 give the operator a one-time setup that produces a recurring trigger; `deploy_windows.bat`'s post-deploy warning will go silent after registration.

**"Still open" items added by this pass**
- **Brand logo CDN** — currently using `apps/web/public/brand/` static asset served from the same Next.js host as the console. Consider Cloudflare R2 or a dedicated logo CDN for production scale so emails can reference an asset that is independent of the app deployment domain.
- **MFA enforcement not yet enabled** — `REQUIRE_MFA_FOR_ADMIN=false` and `ENFORCE_GLOBAL_MFA=false` remain in `.env` pending operator decision and the pre-flight checklist completion documented in runbook §13. Backend logic already honours both flags; flipping them is the only step left.

### 2026-04-28 Phase 6 UX close-out follow-up — sticky banner, readable lineage, auto-advance hardening, conditional CTAs, replay step labels

Second smoke-test session surfaced five more friction points. Issues #6 (display-friendly recommendation ID) and #7 (per-user `risk_dollars_per_trade`) require schema migrations and are deferred to Pass 3 — captured in "Still open" below.

**Section 1 — Sticky Active Trade banner (`apps/web/components/active-trade-banner.tsx` + `console-shell.tsx` + `globals.css`)**
- New `ActiveTradeBanner` client component reads `GuidedFlowState` from URL params via `useSearchParams` (props override is supported but default is URL-driven).
- Renders only when `state.guided === true && state.recommendationId` is present — explorer mode shows nothing, and `/analysis` before generation also shows nothing.
- Layout per spec: `position: sticky; top: 0; z-index: 5`, `#1a2e1f` solid background, 2 px green `#21c06e` bottom border, 10 × 16 padding, flex row with 16 px gap, 14 px font.
- Content: bold green "ACTIVE TRADE:" label, then SYMBOL (white 16 px / 700) · strategy (white) · market mode (muted), spacer, right-side lineage status: `Order staged` / `Replay run #N complete` / `Recommendation created` based on which IDs are populated.
- Mounted in `console-shell.tsx` directly inside `<section className="op-main">` and above `<header className="op-topbar">` so it sits below the sidebar and above the topbar context line. `TopbarContext` is unchanged — this is additive.
- Adjusted `.op-main { grid-template-rows: auto auto 1fr }` so the new banner row + topbar row + content row size correctly.

**Section 2 — Human-readable workflow lineage (`apps/web/lib/lineage-format.ts` + `lineage-format.test.ts` + replay/orders pages)**
- New helper module exports `shortRecommendationId`, `shortReplayRunId`, `shortOrderId`, and `formatLineageBreadcrumb`. The full breadcrumb renders as e.g. `AAPL Event Continuation · Rec #a65757 → Replay #25 → Order pending`.
- `Rec #` shortener: strips a leading `rec_`, keeps the last 6 hex chars; `Order #` shortener: same treatment for `ord_`. Empty/missing inputs return `Replay pending` / `Order pending` / `Rec #—` so the chain never has blank gaps.
- Applied to the Workflow lineage Card body in both `replay-runs/page.tsx` and `orders/page.tsx`. The arrow chain is preserved; only the labels and ID rendering change.
- 14 new vitest unit tests cover prefix stripping, `<= 6 char` ids, missing fields, override precedence, and null-state handling. Fits beside the existing `orders-helpers.test.ts` style — same vitest harness.

**Section 3 — Make active auto-advance hardening (`apps/web/app/(console)/recommendations/page.tsx` + `tests/e2e/phase6-auto-advance.spec.ts`)**
- Code analysis of `promoteSelected()` end-to-end — auto-advance was unreachable only if `promotedRecommendationId` resolved to `undefined`. The backend returns `recommendation_id` at the top level and the api-client unwraps that as `result.data.recommendation_id`, so the existing extraction was correct in the happy path.
- Added defensive triple fallback: `result.data?.recommendation_id ?? result.raw?.recommendation_id ?? selectedQueue?.recommendation_id`. The first works today; the second guards against an upstream wrapping the response in `{ data: {...} }`; the third is a last-resort safety net for the (currently theoretical) case where `selectedQueue` already carries a promoted id.
- Added a temporary `console.debug("[guided] promote success, advancing to replay in 600ms", { promotedId, query })` immediately before the `setTimeout` fires. Marked in-source as "will be removed in next pass" so it does not become a permanent log line.
- New `phase6-auto-advance.spec.ts` Playwright test: mocks `/api/user/recommendations/queue/promote` with a successful response (`recommendation_id: "rec_e2e_advance_abcdef"`), goes to `/recommendations?guided=1&symbol=AAPL`, clicks "Make active", and asserts the URL transitions to `/replay-runs` with both `guided=1` and `recommendation=rec_e2e_advance_abcdef` within 1500 ms.

**Section 4 — Conditional CTA states (`globals.css` + replay/orders pages)**
- New `@keyframes pulse-cta` (0% / 70% / 100% box-shadow ring expansion + fade) and `.op-btn-pulse` class (`animation: pulse-cta 2s infinite`); disabled state suppresses the animation.
- Replay page: in **guided mode only**, derives `replayDoneForRec = Boolean(selectedRunId) || runs.some(r.source_recommendation_id === guidedState.recommendationId)`. When `false`, the always-visible "Run replay now →" carries `op-btn-primary-cta op-btn-pulse` (action needed). When `true`, the button switches to `op-btn op-btn-secondary` with the label `Run again →` (calm; running again is optional). The contextual button inside the "Replaying recommendation" Card always shows `Run replay now →` with pulse because that card only renders when no run exists.
- Orders page: same pattern with `orderDoneForRec` matching by `recommendation_id` or `replay_run_id`. When `false`, "Stage paper order now →" pulses; when `true`, it switches to `Stage another →` secondary.
- Explorer/non-guided mode is intentionally untouched: the conditional collapses to `false`, so the existing primary-CTA styling and copy remain stable. This preserves the `phase1-closeout` non-guided click path.

**Section 5 — Replay step timeline labeling (`apps/web/app/(console)/replay-runs/page.tsx`)**
- Step rows now render `✓ Bar #{step_index + 1}` (green) for approved and `✗ Bar #{step_index + 1}` (red) for rejected — addresses the operator's confusion about "step 0 vs step 1" by switching to one-indexed bar numbering with a visual approval icon.
- New `fmtStepTimestamp` helper formats an optional `step.timestamp` ISO string as `YYYY-MM-DD HH:MM` UTC; appended after the bar label as a muted `· {timestamp}` chip when present.
- An optional `step.event_text` (when the backend ever populates it) renders as a secondary muted line `Event: {event_text}` directly under the row header.
- The `Step` TS type gained `timestamp?: string | null` and `event_text?: string | null` to keep the rendering forward-compatible without backend changes (deferred per the work-order rule).
- Added a small explainer card at the top of the steps list (always visible when `steps.length > 0`): "Each row shows one bar of historical data the replay engine evaluated. ✓ approved means the recommendation logic would have triggered. ✗ rejected means the bar did not meet the strategy gate. Approved bars contribute to fill simulation."

**Verification**
- `pytest -q` — **173 passed** (unchanged; backend untouched per work-order rules).
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` — **88 passed** across 16 files (was 74 across 15 — added 14 `lineage-format` unit tests).
- `npx playwright test --reporter=list` — **27 passed**, 0 skipped (was 26; added the new Section 3 auto-advance gate). Two pre-existing tests were updated to match the new breadcrumb format: `phase1-closeout.spec.ts` now asserts `Rec #e1-e2e` and `Replay #22`, and `phase5-guided-lineage.spec.ts` now asserts `Rec #orders` / `Replay #10` / `Order pending` instead of the legacy `recommendation:` / `replay run:` / `paper order: —` raw labels.

Still open:
- **Cancel staged order** (Pass 3) — no UI affordance or backend endpoint to cancel a staged paper order before a fill occurs.
- **Reopen closed position** (Pass 3) — no way to undo a closed trade. Realized P&L is permanent on close.
- **Display-friendly recommendation ID** (Pass 3) — alongside the canonical `rec_<hex>` token, surface a human-meaningful identifier such as `AAPL-EVCONT-20260428-1430`. Requires a schema migration on the recommendations table to persist the slug deterministically; deferred to a later pass.
- **Per-user `risk_dollars_per_trade` configuration** (Pass 3) — currently env-only via `RISK_DOLLARS_PER_TRADE`, should be settable per operator from a Settings page. Requires a new column on `app_users` plus matching admin/account UI; deferred.

### 2026-04-28 Phase 6 UX close-out — auto-advance + primary CTA

Smoke-test feedback on the guided flow surfaced two friction points: (1) every step required two clicks — the action button (Make active / Run replay now / Stage paper order) and a separate "Go to X step" navigation button — which is ceremony, not control, in guided mode; and (2) the primary CTA did not visually dominate the page, so the operator's eye did not land on it within ~1 second.

**Section 1 — Auto-advance on guided action success**

Applies only when `guidedState.guided === true`. Explorer-mode behavior unchanged.

- `apps/web/app/(console)/recommendations/page.tsx` — after `promoteSelected()` resolves with the `make_active` action, the page calls `router.replace` to update the URL with the newly active recommendation and then `setTimeout(() => router.push(\`/replay-runs?…\`), 600)`. The 600 ms delay keeps the success feedback readable before the route change. The `save_alternative` path does not auto-advance (saving an alternative is an inert lineage operation).
- `apps/web/app/(console)/replay-runs/page.tsx` — after `runReplay()` resolves and a run id is hydrated, the page fetches `/api/user/replay-runs/{id}` to read `has_stageable_candidate`. If `false`, it stays on the page so the warning block (`op-error` block + `stageable_reason`) is visible. Otherwise it auto-advances to `/orders?…` after the same 600 ms delay, threading `recommendation_id`, `replay_run_id`, `symbol`, and `source` through `buildGuidedQuery`.
- `apps/web/app/(console)/orders/page.tsx` — terminal step. After `stagePaperOrder()` resolves, the page hydrates the new order into the blotter, refetches positions/trades, and calls `detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })`. No navigation — the operator is already where they need to be to monitor and close.

**Section 2 — Primary CTA visual treatment (`apps/web/app/globals.css` + 3 page files)**

- New `.op-btn-primary-cta` class in `globals.css`: brand-green background `#21c06e`, white 16 px / 600-weight text, 12 × 20 padding, 6 px radius, no border, `min-width: 220px`, soft green box-shadow `0 2px 8px rgba(33,192,110,0.2)`. Hover lifts (`translateY(-1px)`) and intensifies the shadow. Disabled drops to 0.5 opacity, `not-allowed` cursor, muted-green background `#4a5a4a`, transform reset.
- Applied on each guided page to the actual primary action button:
  - **Recommendations** "Next action" Card → `Make active` (the `Save as alternative` sibling stays as `op-btn-secondary`).
  - **Replay** → both `Run replay now` instances (the contextual one in the "Replaying recommendation" Card hero and the always-visible one in the action Card below).
  - **Orders** → both `Stage paper order now` instances (the contextual one in the "Paper order ticket" Card hero and the always-visible one in the action Card below).
- After every primary CTA label, appended a right-arrow ` →` so directional intent is visible at a glance ("Make active →", "Run replay now →", "Stage paper order now →").
- The `Go to X step` navigation buttons keep their existing default / `op-btn-secondary` / `op-btn-ghost` styling — they are manual overrides, not the primary path, and should remain visually subordinate.

**Verification**
- `pytest -q` — 173 passed (unchanged; backend untouched per work-order rules).
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` — 74 vitest tests across 15 files (unchanged).
- `npx playwright test --reporter=list` — **26 passed**, 0 skipped. No assertion updates required: existing tests address buttons by visible label or `getByRole("button", { name: /Run replay now/ })`, which still match after the ` →` suffix is appended.

Still open:
- **Cancel staged order** — there is no UI affordance or backend endpoint to cancel a staged paper order before a fill occurs. An operator who mis-stages has no undo path.
- **Reopen closed position** — there is no way to undo a closed trade. Realized P&L is permanent on close, with no operator-reversible escape hatch for a misclick or a wrong mark price.

### 2026-04-28 Phase 5 final closeouts + Phase 6 close-flow e2e

Three sections in one pass: role-conditional sidebar (real bug fix), strategy regime hints, and 9 new Playwright e2e tests gating the Phase 6 close lifecycle.

**Section 1 — Role-conditional sidebar (`apps/web/components/console-shell.tsx`)**
- Existing code already gated the Admin section on `appRole === "admin"` and started with `null`, but the resolution path was implicit: a 401/error left the prior role intact, and there was no explicit "fetch settled" signal to distinguish "still loading" from "loaded as non-admin."
- Refactored to track both `appRole` and a `meChecked` boolean. The Admin section now renders only when `meChecked && appRole === "admin"` — a single derived `isAdmin` flag drives the conditional. On 401, network error, or any non-OK response, both `setAppRole(null)` and `setMeChecked(true)` fire (fail-closed: settled but not admin). During the in-flight initial fetch, `meChecked` is false so Admin is hidden — no flicker for non-admin users.

**Section 2 — Strategy selector regime hints (`apps/web/app/(console)/analysis/page.tsx`)**
- Hint block under the strategy `<select>` rewritten to spec: `description` on its own line, optional `regime_fit` rendered as a separate line prefixed `Best in: …` (was previously inline-appended after a middot).
- Styling aligned to the work-order spec: `font-size: 12px`, `color: var(--op-muted, #7a8999)`, `lineHeight: 1.4`, no card chrome (it's an inline hint, not a panel). Added `data-testid="strategy-hint"` for future test addressability.
- Updates on every strategy change without requiring a Refresh — `selectedStrategyEntry` is already a `useMemo` over `strategiesForDraftMode + draftStrategy`, so the hint follows the dropdown live.
- Renders nothing when the registry entry has no `description` (no placeholder copy), per spec.

**Section 3 — Phase 6 close-lifecycle e2e (`apps/web/tests/e2e/phase6-close-lifecycle.spec.ts`)** — 9 new tests, all passing on first run:

1. *Open positions list renders after fill* — mounts `/orders?guided=1` with one mocked open position carrying full lineage; asserts Card heading, row data (symbol, `op-side-badge.is-long`, qty, avg entry, recommendation `<Link>`, Close button), and the Closed-trades empty-state copy.
2. *Open positions empty state* — mocks empty positions list; asserts `"No open paper positions"` copy and zero Close buttons inside the Open positions card.
3. *Close ticket opens inline below row* — clicks Close; asserts the ticket is a sibling row inside the same Card (not a modal), `mark_price` input defaults to `avg_entry_price.toFixed(2)`, reason `<select>` lists exactly the five spec'd options in order, Confirm + Cancel buttons present.
4. *Cancel dismisses without POST* — uses a request-method counter on the close-route mock; asserts the POST count stays at 0 and the ticket disappears.
5. *Close success refetches lists + surfaces realized PnL* — three counter-backed mocks (positions GET, trades GET, portfolio-summary GET); confirms close, asserts the InlineFeedback success message contains `+142.50`, asserts each counter increments past mount-only baseline.
6. *Closed trade row appears after close* — sequenced trades mock returns `[]` initially and `[newTrade]` on the post-close refetch; asserts the closed-trades Card row populates with symbol, qty, `entry_price → exit_price`, color-coded realized PnL, hold duration (`2h 14m`), and reason.
7. *Realized PnL color coding* — mocks one positive + one negative trade; asserts `toHaveCSS("color", "rgb(33, 192, 110)")` for the positive and `rgb(224, 122, 122)` for the negative (exact rgb equivalents of `#21c06e` / `#e07a7a` from `pnlColor`).
8. *Workflow lineage card extension* — two orders + one matching open position + one matching closed trade; clicks each order row in turn; asserts the lineage card appends `↳ open position #{id}` for the open match and `↳ closed trade #{id} · realized {±N.NN}` for the closed match.
9. *Close error surfaces InlineFeedback, ticket stays open* — mocks the close POST as 400 with `"Position already closed"`; asserts the error message renders, the ticket stays open (mark_price input + Confirm button still visible), and positions/trades GET counters do **not** increment past their pre-close values (no silent refetch on error).

All 9 use the existing `beforeEach` catch-all + `/api/user/me` mock pattern and per-test `page.route` overrides — no new infrastructure.

**Verification**
- `pytest -q` — 173 passed (unchanged; backend untouched per work-order rules).
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` — 74 vitest tests across 15 files (unchanged).
- `npx playwright test --reporter=list` — **26 passed** (was 17), 0 skipped.

**Roadmap "Still open" items this pass closes**
- "Strategy selector enhancement: description + regime hint per entry from strategy-registry endpoint" — closed.
- "Playwright e2e coverage for the close lifecycle (separate gate per the work order)" — closed (9 tests in `phase6-close-lifecycle.spec.ts`).

### 2026-04-28 Phase 6B — close-trade lifecycle UI on /orders + CSS selector cleanup

Surfaces the Phase 6A backend foundation in the operator console. No backend changes (Phase 6A contract is locked).

**CSS selector cleanup (`apps/web/app/globals.css`)**
- The 2026-04-28 cosmetic pass added `tr.is-approved` / `tr.is-rejected` selectors, but the replay step DOM uses `<div>` not `<tr>`, so the row tints never rendered. Selectors changed to `.is-approved` / `.is-rejected` (tag-agnostic) so the existing `is-approved` / `is-rejected` className applications on replay step cards now activate. DOM unchanged — no `<div>` → `<tr>` refactor.

**Next.js proxy routes (mirroring the existing `app/api/user/...` pattern)**
- `apps/web/app/api/user/paper-positions/route.ts` — GET → `/user/paper-positions`, forwards `status` and `limit` query params via `includeSearchParams: true`.
- `apps/web/app/api/user/paper-positions/[positionId]/close/route.ts` — POST → `/user/paper-positions/{id}/close`, forwards request body intact.
- `apps/web/app/api/user/paper-trades/route.ts` — GET → `/user/paper-trades`, forwards `limit` via `includeSearchParams: true`.
- All three reuse `proxyWorkflowRequest` from `_utils/workflow-proxy.ts` and inherit its auth-token resolution + 425 auth-initializing handling.

**Open positions Card on /orders (`apps/web/app/(console)/orders/page.tsx`)**
- New `Card` titled "Open paper positions" rendered above the existing Order history grid.
- Fetches `GET /api/user/paper-positions?status=open` on mount (`useEffect` keyed on `searchKey, authReady`) and after every successful order stage and position close.
- Each row shows: symbol · side (`op-side-badge` reused from 2026-04-28 cosmetic pass) · `remaining_qty` · `avg_entry_price` (2 decimals) · opened (relative time via new `formatRelativeTime`) · recommendation lineage (clickable `<Link>` to `/recommendations?…` preserving `guidedState` via `buildGuidedQuery`) · "Close position" button.
- Empty state: `<EmptyState title="No open paper positions" hint="Stage a paper order from a replay-validated recommendation to open a position." />`.

**Inline close ticket (no modal — matches existing console pattern)**
- Click "Close position" → row stays in place; an additional `<tr>` opens immediately below it inside the same table.
- Ticket fields: `mark_price` `<input type="number" required>` (default = position's `avg_entry_price`), `reason` `<select>` with options `Target hit` / `Stop hit` / `Manual exit` / `Time exit` / `Other`.
- Confirm → `POST /api/user/paper-positions/{id}/close` with `{ mark_price, reason }`. On success: refetches positions list, trades list, and portfolio summary in parallel; surfaces realized P&L in the `InlineFeedback` success message. On error: error feedback with the upstream message.
- Cancel → resets ticket state without sending.
- State: `closingPositionId`, `closeMarkInput`, `closeReasonInput` (`useState`), with `beginClosePosition` / `cancelClosePosition` / `confirmClosePosition` handlers.

**Closed trades Card on /orders**
- New `Card` titled "Closed trades (last 50)" rendered below the order history grid.
- Fetches `GET /api/user/paper-trades?limit=50` on mount and after every close.
- Columns: symbol · side (`op-side-badge`) · qty · `entry → exit` · realized P&L (color from `pnlColor`: green positive, red negative, inherit zero — bold) · hold (human duration via `formatHoldDuration`) · close reason · closed (relative time).
- Empty state: "No closed trades yet."

**Workflow lineage card extension**
- Existing "Workflow lineage" card now appends a second line when `selected.order_id` matches an entry in either the open positions list or the closed trades list:
  - Open match → `↳ open position #{id}`.
  - Closed match → `↳ closed trade #{id} · realized {±N.NN}` with `pnlColor` styling on the value.
- Both lines render side-by-side (separated by `·`) when an order has been closed but a fresh open also exists; either alone otherwise. No render when no match (so non-equity / not-yet-filled orders stay untouched).

**Helpers (`apps/web/lib/orders-helpers.ts`)**
- `pnlColor(pnl)` → `#21c06e` / `#e07a7a` / `inherit` for positive / negative / zero. Reused by closed-trades P&L cell and lineage extension.
- `formatHoldDuration(seconds)` → `<1m` / `Nm` / `Nh Mm` / `Nd Mh`. `null`/`undefined`/negative → `—`.
- `formatRelativeTime(iso, nowMs?)` → `just now` / `Nm ago` / `Nh ago` / `Nd ago`. Returns the original ISO string for future-dated or unparseable input.

**Vitest unit tests (`apps/web/lib/orders-helpers.test.ts`)** — 15 new tests across the three helpers:
- `pnlColor` — positive / negative / zero branches.
- `formatHoldDuration` — null / undefined / negative input → em-dash; sub-minute → `<1m`; sub-hour minutes; sub-day with both `Nh Mm` and `Nh` (zero-minute) variants; multi-day with both `Nd Mh` and `Nd` (zero-hour) variants.
- `formatRelativeTime` — null / undefined input; `just now`; minutes / hours / days; future-dated input passes through; unparseable input passes through.

**Verification**
- `pytest -q` — 173 passed (unchanged from Phase 6A — backend untouched).
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` — **15 vitest files, 74 tests** (was 14 / 59).
- Playwright untouched this pass — 17 e2e remain green from prior runs (e2e for the close flow is documented as a separate gate in the work order).

**Still open (deferred per work-order rules)**
- Commission and slippage modeling on close (the prompt explicitly excluded this from Phase 6B; tracked for a future pass).

### 2026-04-28 Phase 6A — close-trade lifecycle backend foundation + Phase 5 cosmetic closeouts

Backend foundation for explicit position lifecycle tracking and close-trade auditability. Frontend untouched aside from two scoped Phase 5 cosmetic closeouts at the end of this pass.

**Part 1 — Auto-create paper_position on order fill (`api/routes/admin.py`, `storage/repositories.py`, `domain/models.py`)**
- `PaperPositionModel` extended with nullable lineage columns: `opened_qty`, `remaining_qty`, `recommendation_id`, `replay_run_id`, `order_id`. (`apply_schema_updates` auto-adds them on the live SQLite DB at startup; existing `quantity` / `average_price` columns retained for back-compat with `PaperPortfolioRepository.summary`.)
- `PaperTradeModel` extended with: `position_id`, `hold_seconds`, `recommendation_id`, `replay_run_id`, `order_id`, `close_reason`.
- New `PaperPortfolioRepository.upsert_position_on_fill(...)` — looks up the open `(app_user_id, symbol, side)` position and either aggregates the new fill into it (recomputing `average_price` as the qty-weighted average of the prior cost basis and the new fill, advancing `opened_qty` and `remaining_qty`) or creates a new row. Lineage columns set on creation only — aggregation does not overwrite the originating recommendation/replay/order ids.
- `stage_order` now calls `upsert_position_on_fill` with the actual fill price/shares and lineage ids when `market_mode == EQUITIES` and `fill.filled_shares > 0` (replaces the prior `if order.side.value == "long"` branch that created a position from `order.limit_price` without lineage). Non-equities orders are skipped per Phase 1 scope.

**Part 2 — Close position endpoint (`POST /user/paper-positions/{position_id}/close`)**
- Body: `{ "mark_price": float, "reason": str | null }`. Validates `mark_price` is numeric (400 otherwise).
- Owner-scoped: 404 when the position id does not exist or belongs to a different user (matches the scope-isolation pattern elsewhere — does not leak existence).
- 400 when the position is already closed.
- `realized_pnl = (mark_price - avg_entry_price) * remaining_qty` for `long`; sign-flipped for `short` (`* -1`).
- `hold_seconds` computed from `(now - opened_at)`. Normalizes naive `opened_at` (SQLite round-trip) to UTC before subtraction so the math holds whether the row was written this run or read from a persisted DB.
- Creates a `paper_trades` row with full lineage (`position_id`, `hold_seconds`, `recommendation_id`, `replay_run_id`, `order_id`, `close_reason`), then closes the position (`status="closed"`, `closed_at=now`, `remaining_qty=0`, `quantity=0`).
- Returns the serialized trade row.

**Part 3 — List endpoints (owner-scoped)**
- `GET /user/paper-positions?status=open|closed|all&limit=50` — ordered by `opened_at desc`. 400 on bad `status`.
- `GET /user/paper-trades?limit=50` — ordered by `closed_at desc`.
- New `_serialize_position` / `_serialize_trade` helpers in `admin.py` produce the JSON shapes (using spec field names: `opened_qty`, `remaining_qty`, `avg_entry_price`, `qty`, `close_reason`, etc.).

**Part 4 — Tests (`tests/test_close_trade_lifecycle.py`)**
Seven new pytest cases — full suite **166 → 173 passing**:
1. `test_order_fill_creates_paper_position_with_lineage` — staging an order creates an open position with `recommendation_id` and `order_id` populated.
2. `test_multiple_fills_aggregate_with_weighted_average` — two `stage_order` calls on the same `(user, symbol, side)` aggregate into one position row with cumulative `opened_qty`/`remaining_qty` and weighted-avg entry preserved.
3. `test_close_position_realized_pnl_long` — long PnL math + close response shape + post-close position state.
4. `test_close_position_realized_pnl_short` — short position seeded directly via the ORM (short orders don't flow through `stage_order` in Phase 1) — close endpoint computes `(mark - avg) * qty * -1` and returns +PnL when `mark < avg`.
5. `test_close_position_blocks_non_owner_with_404` — admin-token user attempting to close a `clerk_user`-owned position → 404 with `"Position not found."`.
6. `test_close_position_already_closed_returns_400` — second close attempt → 400 with `"Position is already closed."`.
7. `test_list_endpoints_scope_to_owning_user` — User A closes a position; User B's `paper-positions?status=all` and `paper-trades` lists are both empty; A's lists still contain the row.

**Part 5 — Phase 5 cosmetic closeouts (`apps/web/app/globals.css`, `apps/web/app/(console)/orders/page.tsx`, `apps/web/app/(console)/replay-runs/page.tsx`)**
- `globals.css` gains `.op-side-badge` base style plus `.is-buy` / `.is-sell` (and equivalent `.is-long` / `.is-short` for the canonical `Direction` enum the backend emits) — green for buy/long, red for sell/short. Plus `tr.is-approved { background: rgba(33, 192, 110, 0.06); }` and `tr.is-rejected { background: rgba(224, 122, 122, 0.06); }`.
- Orders table side cell: `<StatusBadge tone=...>` replaced with `<span className={\`op-side-badge is-${o.side.toLowerCase()}\`}>{o.side}</span>` — visible green/red BUY/SELL chips at a glance. Side cells in the selected-order detail panel keep `StatusBadge` (the prompt scoped this change to the table column).
- Replay step cards now carry `is-approved` / `is-rejected` className alongside the existing `borderLeft` color cue. The CSS rules in `globals.css` use `tr.` selectors per the work order spec; activation is gated until step rows refactor from `<div>` to `<tr>` — applied className is in place for that future change.

**Verification**
- `pytest -q` — **173 passed** in ~14s (was 166).
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` — 14 vitest files, 59 tests green.
- `npx playwright test --reporter=list` — 17 passed, 0 skipped.

**Roadmap "Still open" items this pass closes**
- Operator runbook reference: "Full close-trade UI for existing closed orders without in-session closeResults" — the backend foundation is now in place; UI surfacing is a follow-up pass.

### 2026-04-28 Phase 5 polish — refreshAnalysis URL push + e2e unskip

Closes the gap surfaced by the prior pass's `test.skip`: `/analysis` now mirrors applied symbol/strategy/market_mode/source into the URL after a successful Refresh, so `TopbarContext`, deep-links, and guided handoff all stay in sync.

**Fix — `refreshAnalysis` pushes URL on success (`apps/web/app/(console)/analysis/page.tsx`)**
- `runAnalysis` now returns `Promise<string | null>`: the resolved workflow source string on success, or `null` on any early-return / catch path. All early-return branches (auth not ready, 402 data-not-entitled, 503 provider-unavailable, hard failure, AUTH_NOT_READY catch, generic catch) return `null`. The success branch returns `payload.fallback_mode ? "fallback (...)" : payload.data_source` (with `setupPayload.workflow_source` and `"workflow source pending"` as ordered fallbacks).
- `refreshAnalysis` awaits `runAnalysis(...)`, returns early if `workflowSource == null`, then builds a query via `buildGuidedQuery({ guided: guidedMode, symbol: nextSymbol, strategy: draftStrategy, marketMode: draftMarketMode, source: workflowSource })` and calls `router.replace(\`/analysis?${query}\`)`. Empty query falls back to `/analysis`.
- Reuses `buildGuidedQuery` from `@/lib/guided-workflow` — same canonical helper already used by `createRecommendation`.
- `router.replace` (not `push`) — Refresh is idempotent state hydration, not a history-worthy navigation.
- Pushes only after a successful setup fetch (not on error/loading), per the work order.
- In explorer mode, the push omits `guided=1` (because `buildGuidedQuery` only emits it when `state.guided === true`) — deep-linking to `/analysis?symbol=AAPL&strategy=Event+Continuation&market_mode=equities&source=polygon` works in both guided and explorer modes.
- The two `useEffect` callers of `runAnalysis` (initial-load on auth-ready, and indicator-change) intentionally do **not** push — only the explicit Refresh click does. This keeps the user landing on `/analysis?guided=1` from having their URL silently rewritten before they interact.

**E2E test unskipped (`apps/web/tests/e2e/phase5-guided-lineage.spec.ts`)**
- The previously-skipped `test.skip("guided /analysis topbar reflects applied symbol after Refresh analysis (gap: form state not pushed to URL)")` is converted to an active `test`. TODO comment removed.
- Test flow: navigate to `/analysis?guided=1` → assert pre-refresh topbar text → wait for initial setup load (the mock's distinctive `active_reason: "phase5 url-push"` proves Clerk auth and setup hydration completed before clicking Refresh) → click `analysis-refresh-button` → assert URL now contains `symbol=AAPL`, `strategy=Event+Continuation`, `guided=1` → assert TopbarContext text "AAPL · Event Continuation" is visible.
- Wait gate is essential: if the Refresh click fires before Clerk's `isLoaded` settles, `runAnalysis` returns `null` at the auth-not-ready branch and no URL push occurs. The active-reason wait gates that race deterministically.

**Test fixture fix (same spec file)**
- `chartPayload()` previously generated 40 candles via `idx % 28`, producing duplicate dates after index 28 and tripping lightweight-charts' "data must be asc ordered by time" assertion when the chart actually rendered (which only the unskipped Refresh-success test exercises). Replaced with strictly ascending dates: indices 0–30 → `2026-01-01..2026-01-31`, indices 31–39 → `2026-02-01..2026-02-09`.

**Verification**
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` — 14 vitest files, 59 tests green.
- `npx playwright test --reporter=list` — **17 passed, 0 skipped** in ~50s. Prior 16 tests still green; the unskipped test now passes.
- Backend untouched — pytest count remains 166.

**Roadmap "Still open" items this pass closes**
- "`refreshAnalysis` should push `symbol` / `strategy` to the URL so `TopbarContext` reflects post-refresh selection without a separate navigation" — closed; URL push now wired and the e2e regression guard is active.

### 2026-04-28 Phase 5 polish — Playwright e2e for guided lineage + empty states

Pure test-layer pass: nine new e2e tests (eight active + one documented `test.skip`) added in `apps/web/tests/e2e/phase5-guided-lineage.spec.ts`. **No application code was modified in this pass.**

**Coverage added (regression guards on the 2026-04-28 fixes plus broader empty-state behavior):**
1. Guided `/analysis` hero — `WorkflowBanner` step states (`is-current` / `is-pending`), `TopbarContext` guided-no-symbol hint, `Refresh analysis` CTA enabled, banner chip reflects applied symbol/strategy after refresh.
2. Guided `/recommendations` empty state — "No active recommendation" `EmptyState` renders, queue toggle button shows count, queue table is collapsed by default and expands on click with `AAPL` / `Event Continuation` row data.
3. **Regression for Fix 2 (2026-04-28)** — guided `/recommendations?guided=1&recommendation=rec-missing` with stored items that do NOT match the URL id renders the "No active recommendation" empty state, and the unrelated `rows[0]` recommendation id (`rec-other-msft` / symbol `MSFT`) is asserted absent from the Active recommendation card. Direct guard against silent `rows[0]` fallback re-introducing.
4. Guided `/replay-runs` empty state — when the URL carries `recommendation=rec-nvda-lineage` (no `symbol` param) and the recommendation lineage carries `symbol: NVDA`, the hero card shows `symbol: NVDA` and never falls back to a stale `AAPL`. Recommendation id from lineage is rendered, "Run replay now" CTA is visible and enabled.
5. Replay zero-fill — synthetic run `id=77` with `fill_count: 0` and flat equity (10000 across pre and post) renders "Replay completed, but no fills occurred. Portfolio remained unchanged." and suppresses the equity curve label (distinct equity values < 2).
6. Replay stageability gating — synthetic run `id=55` with `has_stageable_candidate: false` renders the `op-error` styled "Replay produced no stageable candidate" block and the `stageable_reason` text inside the same block.
7. Guided `/orders` empty state — hero "No paper order staged yet" renders, "Stage paper order now" CTA visible, and the "Workflow lineage" card threads `recommendation: rec-lineage-orders → replay run: 10 → paper order: —`.
8. **Regression for Fix 1 (2026-04-28)** — three URL navigations verify `TopbarContext` text directly: `/analysis` → "Explorer mode"; `/analysis?guided=1` → "Guided workflow — start at Analyze"; `/analysis?guided=1&symbol=NVDA&strategy=Event%20Continuation` → "NVDA · Event Continuation". Pure URL-driven, no form interaction.

**Skipped with TODO (gap surfaced by Test 1):**
- `guided /analysis topbar reflects applied symbol after Refresh analysis (gap: form state not pushed to URL)` — closed in the follow-up 2026-04-28 pass above (URL push wired, test unskipped and passing).

**Test count**
- Before: 8 Playwright tests (in `phase1-closeout.spec.ts` + `guided-workflow-hero.spec.ts`).
- After: **17 Playwright tests** — 16 passing + 1 documented skip (the skip was closed in the next 2026-04-28 pass).
- Backend untouched — pytest count remains 166.

**Roadmap "Still open" items this pass closes**
- "Broader component-level frontend tests for all guided hero variants beyond current e2e coverage" → guided hero variants on Analyze, Recommendations, Replay, and Orders are now all covered.
- "Playwright coverage for the enhanced guided lineage hero cards and replay/order immediate post-create hydration" → empty-state heroes for replay (no run yet) and orders (no order staged) are now covered, plus the lineage-symbol propagation through to `/replay-runs`.

### 2026-04-28 Phase 5 polish — topbar context + guided lineage strictness

Three targeted Phase 5 polish fixes; no scope expansion.

**Fix 1 — Topbar active-context line (`apps/web/components/console-shell.tsx`, `apps/web/components/topbar-context.tsx`)**
- `topbar-context.tsx` rewritten to read `useSearchParams` + `usePathname` and parse guided state via `parseGuidedFlowState` (canonical helper). The static workflow string ("Workflow: Analyze → Recommendation → Replay → Paper Order") is gone.
- Display logic:
  - `guided=1` and `symbol` present → renders `{SYMBOL} · {strategy if present}` (uppercased symbol).
  - `guided=1` and no `symbol` → renders `Guided workflow — start at Analyze`.
  - Not guided → renders `Explorer mode`.
  - Raw query string is never rendered.
- `console-shell.tsx` already mounts `<TopbarContext />` in the topbar slot next to `<BrandLockup compact />`; no styling or class changes were needed.
- `Suspense` fallback updated to `Explorer mode` (matches the no-guided default rather than the legacy workflow string).

**Fix 2 — No silent rows[0] fallback in guided mode (`apps/web/app/(console)/recommendations/page.tsx`)**
- `activeRecommendation` `useMemo` updated: when `guidedState.guided` is true and there is no match for `guidedState.recommendationId` in `rows`, return `null` to force the empty state ("No active recommendation"). When not guided, the existing `rows[0]` fallback is preserved.
- This honors the "no silent fabrication of workflow data" rule — guided lineage must always be explicit.

**Fix 3 — Hide duplicate promote button in guided mode (`apps/web/app/(console)/recommendations/page.tsx`)**
- The "Promote selected queue candidate" button in the bottom-row symbols-input action card is now wrapped in `!guidedState.guided` so it only renders in explorer mode. In guided mode, the canonical CTA is the Next-action card's "Make active" / "Save as alternative" pair.
- "Refresh queue" and "Go to Replay step" remain visible in both modes; "Go to Paper Order step" stays explorer-only as before.

**Verification**
- `npx tsc --noEmit` clean in `apps/web`.
- `npm test` passes — 14 test files, 59 vitest tests green.
- No Playwright tests added in this pass (separate track per the work order).
- Backend untouched — pytest count remains 166.

### 2026-04-16 DataNotEntitledError — Polygon 403 / plan-gated data

**`DataNotEntitledError` and HTTP 402 (`market_data.py`, `admin.py`, `analysis/page.tsx`)**
- `DataNotEntitledError(Exception)` added to `market_data.py` — third distinct exception class alongside `ProviderUnavailableError` and `SymbolNotFoundError`.
- `_fetch_url`: HTTP 403 → `DataNotEntitledError("Not entitled to this data. Upgrade plan at https://polygon.io/pricing")`.
- `MarketDataService.historical_bars` and `latest_snapshot`: re-raise `DataNotEntitledError` (added to existing `(SymbolNotFoundError, DataNotEntitledError)` tuple).
- `_workflow_bars` in `admin.py`: new `except DataNotEntitledError` branch before `SymbolNotFoundError` → HTTP 402 `{ "error": "data_not_entitled", "message": "Your data plan does not include {symbol}. Index bar data (SPX, NDX, VIX) requires a plan upgrade." }`.
- Frontend `analysis/page.tsx`: 402 response → `workbenchState = "data_not_entitled"`. Dedicated `StatusBadge tone="warn"` banner: "Data not available for {symbol} on current plan. Try SPY instead of SPX, or QQQ instead of NDX." Provider-unavailable banner not shown for 402. `WorkbenchState` union extended with `"data_not_entitled"`.

**Backend tests (3 new → 166 total)**
- `test_data_not_entitled_raised_on_polygon_403`: patches module-level `urlopen` to raise `HTTPError(403)`; confirms `DataNotEntitledError` propagates out of `fetch_historical_bars`.
- `test_market_data_service_propagates_data_not_entitled`: service does not fall back when provider raises `DataNotEntitledError`.
- `test_workflow_bars_returns_402_for_entitled_data`: full route test via `TestClient`; confirms 402 with `error: data_not_entitled` and symbol in message.

166 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-16 Polygon options chain preview + index symbol fixes

**Fix 3 — Options chain preview for research-preview mode (`market_data.py`, `admin.py`, `analysis/page.tsx`)**
- `PolygonMarketDataProvider.fetch_options_chain_preview(symbol, limit=50)` — calls `GET /v3/reference/options/contracts` with `sort=expiration_date&order=asc&expired=false`. Finds nearest expiry, returns up to 5 calls and 5 puts `{ strike, expiry, last_price: null, volume: null }`. On 404/empty/unavailable returns `{ reason: "...", calls: null, puts: null }`.
- `MarketDataService.options_chain_preview(symbol, limit)` — delegates to Polygon provider; returns `None` for non-Polygon providers (fallback/Alpaca).
- `analysis_setup` in `admin.py`: when `market_mode == OPTIONS`, adds `options_chain_preview` key to payload (either chain dict or `None`).
- Frontend `SetupPayload` type updated with `options_chain_preview` field.
- Analysis page: "Options chain preview" card rendered when mode is options — shows calls/puts table or graceful reason message. Uses existing `op-card` + `op-table` styling; no new CSS.

**Fix 2 (addendum) — OEX added to INDEX_SYMBOLS**
- `INDEX_SYMBOLS` now includes `{"SPX", "NDX", "RUT", "VIX", "DJI", "COMP", "OEX"}`.

**Backend tests (5 new → 163 total)**
- `test_options_chain_preview_returns_calls_and_puts`: mock reference endpoint; verifies `expiry`, `source`, call/put structures.
- `test_options_chain_preview_null_when_no_results`: empty results → `calls: null`, `puts: null`, `reason` set.
- `test_options_chain_preview_null_when_provider_unavailable`: `ProviderUnavailableError` → graceful reason dict.
- `test_analysis_setup_includes_options_chain_preview_for_options_mode`: full route test confirming `options_chain_preview` in payload with correct shape.
- `test_analysis_setup_options_chain_preview_none_when_provider_not_polygon`: non-Polygon stub returns `null`; payload key present but value is `null`.

163 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-16 Polygon symbol handling fixes

**Fix 1 — Distinguish "provider down" from "symbol not found" (`market_data.py`, `admin.py`)**
- `SymbolNotFoundError(Exception)` added to `market_data.py` — separate from `ProviderUnavailableError`.
- `PolygonMarketDataProvider._fetch_url`: HTTP 404 now raises `SymbolNotFoundError` (not `ProviderUnavailableError`).
- `PolygonMarketDataProvider.get_historical_bars`: raises `SymbolNotFoundError` when results count == 0 after pagination.
- `PolygonMarketDataProvider.get_latest_snapshot`: raises `SymbolNotFoundError` when `ticker` is None.
- `MarketDataService.historical_bars` / `latest_snapshot`: re-raise `SymbolNotFoundError` instead of falling back to deterministic bars.
- `_workflow_bars` in `admin.py`: catches `SymbolNotFoundError`, returns HTTP 400 `{ "error": "symbol_not_found", "message": "No data found for symbol {symbol}. Verify the ticker is correct and supported." }`.

**Fix 2 — Index symbol support (`market_data.py`)**
- `INDEX_SYMBOLS = {"SPX", "NDX", "RUT", "VIX", "DJI", "COMP"}` — known indices requiring Polygon `I:` prefix.
- `normalize_polygon_ticker(symbol)` — maps index symbols to `I:{symbol}`, passes all others unchanged; case-insensitive.
- Applied in `get_historical_bars` and `get_latest_snapshot` before constructing Polygon URLs.

**Backend tests (7 new → 158 total)**
- `test_normalize_polygon_ticker_maps_index_symbols`: all INDEX_SYMBOLS get prefix; equity symbols pass through.
- `test_polygon_historical_bars_uses_normalized_ticker`: SPX request sends `I:SPX` in URL path.
- `test_polygon_snapshot_uses_normalized_ticker`: VIX snapshot request sends `I:VIX` in URL path.
- `test_symbol_not_found_raised_when_polygon_returns_empty_results`: empty results → `SymbolNotFoundError`.
- `test_symbol_not_found_raised_when_polygon_snapshot_missing`: null ticker → `SymbolNotFoundError`.
- `test_market_data_service_propagates_symbol_not_found`: service does not fall back on `SymbolNotFoundError`.
- `test_workflow_bars_returns_400_for_unknown_symbol`: full route test via `TestClient`; confirms 400 with `error: symbol_not_found`.

158 pytest passing. `npx tsc --noEmit` clean (no frontend changes).

### 2026-04-16 Admin user management hardening pass 2

Five more admin hardening fixes across backend, proxy routes, and UI.

**Fix 1 — Sign-up error boundary**
- `apps/web/app/sign-up/[[...sign-up]]/error.tsx` — route-level boundary with "Try again" + "Go to sign in" links; logs `error.digest`.
- `apps/web/app/global-error.tsx` — root-level boundary with full `<html>` wrapper for truly unrecoverable errors.

**Fix 2 — Unsuspend / re-approve (`admin.py`, `[userId]/unsuspend/route.ts`, `admin-users-panel.tsx`)**
- `POST /admin/users/{user_id}/unsuspend` — sets `approval_status → approved`; 409 if targeting self.
- Frontend: `apps/web/app/api/admin/users/[userId]/unsuspend/route.ts` POST proxy.
- `approve_user` already accepts rejected users; both paths covered.

**Fix 3 — Hard delete user (`admin.py`, `repositories.py`, `[userId]/route.ts`, `admin-users-panel.tsx`)**
- `DELETE /admin/users/{user_id}` — 409 if self, 404 if not found; removes local DB record.
- `UserRepository.delete_user()` + `get_by_id()` added.
- Frontend: `apps/web/app/api/admin/users/[userId]/route.ts` DELETE proxy.
- UI: "Delete" button in expanded row with two-step inline confirm ("Permanently delete {name}? This cannot be undone.").

**Fix 4 — Force re-login via Clerk session invalidation (`admin.py`, `[userId]/force-password-reset/route.ts`, `admin-users-panel.tsx`)**
- `POST /admin/users/{user_id}/force-password-reset` — calls `DELETE /v1/users/{clerk_id}/sessions`; 409 if self or no active Clerk identity; 502 on Clerk failure.
- Frontend: `apps/web/app/api/admin/users/[userId]/force-password-reset/route.ts` POST proxy.
- UI: "Force re-login" button in expanded row (visible for approved/suspended users only).

**Fix 5 — Status-aware action matrix (`admin-users-panel.tsx`)**
- Main row actions: `approved` → Suspend + Make admin/user; `suspended` → Unsuspend; `rejected` / `pending` → Approve; `pending` → +Reject.
- Expanded row actions: Force re-login (approved/suspended only) + Delete with two-step confirm (all statuses).
- Own row: mutating actions hidden with `title="Cannot modify your own account"` tooltip.

**Backend tests (5 new → 151 total)**
- `test_re_approve_suspended_user`: suspend then unsuspend via `/unsuspend`; access restored.
- `test_re_approve_rejected_user`: rejected → approved via standard `/approve`; access granted.
- `test_delete_user_scoped_to_admin`: non-admin blocked (403), admin succeeds, second delete 404.
- `test_delete_user_cannot_target_self`: 409 on self-delete.
- `test_force_relogin_calls_clerk_session_invalidation`: monkeypatches `httpx.delete`; verifies correct Clerk URL called.

151 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-16 Admin user management hardening pass

Six admin actions added across backend, proxy routes, and UI.

**Fix 1 — Approve/reject email non-blocking**: Already complete from prior session. No change.

**Fix 2 — Delete/revoke an invite (`admin.py`, `repositories.py`, `[inviteId]/route.ts`, `pending-users-panel.tsx`)**
- `DELETE /admin/invites/{invite_id}` — deletes the invite record; 404 if not found; scoped to admin.
- `InviteRepository.delete()` + `get_by_id()` methods added.
- Frontend: `apps/web/app/api/admin/invites/[inviteId]/route.ts` DELETE proxy.
- UI: "Revoke" button per invite row with inline confirm/cancel flow.

**Fix 3 — Resend an invite (`admin.py`, `repositories.py`, `models.py`, `[inviteId]/resend/route.ts`, `pending-users-panel.tsx`)**
- `AppInviteModel` gains nullable `sent_at` column (picked up by `apply_schema_updates`).
- `POST /admin/invites/{invite_id}/resend` — re-sends invite email, updates `sent_at`.
- `InviteRepository.update_sent_at()` method added.
- Frontend: `apps/web/app/api/admin/invites/[inviteId]/resend/route.ts` POST proxy.
- UI: "Resend" button per invite row; disabled 5 seconds after click; "Invite resent" badge on success.

**Fix 4 — Change user role (`admin.py`, `repositories.py`, `[userId]/set-role/route.ts`, `admin-users-panel.tsx`)**
- `POST /admin/users/{user_id}/set-role` — body `{ role: "admin" | "user" }`; 409 if targeting self.
- `UserRepository.set_app_role()` + `get_by_id()` methods added.
- Frontend: `apps/web/app/api/admin/users/[userId]/set-role/route.ts` POST proxy.
- UI: "Make admin" / "Make user" toggle per user row; own row disabled.

**Fix 5 — Suspend a user (`admin.py`, `[userId]/suspend/route.ts`, `admin-users-panel.tsx`)**
- `POST /admin/users/{user_id}/suspend` — sets `approval_status → suspended`; 409 if targeting self.
- `ApprovalStatus.SUSPENDED` already existed in enum; console layout already redirected to `/access-denied` for suspended.
- Frontend: `apps/web/app/api/admin/users/[userId]/suspend/route.ts` POST proxy.
- UI: "Suspend" button per row with inline confirm; own row excluded.

**Fix 6 — Expandable user detail row (UI only, `admin-users-panel.tsx`)**
- Click any row to expand: shows email, display name, role, approval, last seen, last auth, Clerk ID + "Copy user ID" button.

**Backend tests (5 new → 146 total)**
- `test_delete_invite_scoped_to_admin`: non-admin blocked (403), admin succeeds, second delete 404.
- `test_resend_invite_updates_sent_at`: `sent_at` null before resend, populated after.
- `test_set_role_cannot_demote_self`: 409 on self, succeeds on another user.
- `test_suspend_cannot_suspend_self`: 409 on self, succeeds on another user.
- `test_suspended_user_blocked_from_console_routes`: approved user gets 200, suspended user gets 403.

**Runbook**: Section 11 added — "User management" reference for all 8 admin actions.

146 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-16 Branded From display name for all outbound emails

**Change — `BRAND_FROM_NAME` env var (`config.py`, `resend.py`, `registry.py`, `.env.example`)**
- `brand_from_name: str = "MacMarket Trader"` added to `Settings` in `config.py`.
- `ResendEmailProvider.__init__` now accepts `from_name` parameter and constructs `from_address` as `"Name <email>"` when a name is provided; falls back to bare email when name is empty.
- `build_email_provider()` in `registry.py` passes `settings.brand_from_name` to `ResendEmailProvider`.
- `.env.example` documents `BRAND_FROM_NAME=MacMarket Trader` with comment explaining inbox display behavior.
- Applies to all outbound emails: invites, approvals, rejections, and strategy reports — all routed through `ResendEmailProvider.send()`.

141 pytest passing. `npx tsc --noEmit` clean (no frontend changes).

### 2026-04-15 Fix: email send no longer blocks approve/reject actions

**Bug:** `approve_user` and `reject_user` called `email_provider.send()` without a try/except — any email failure (bad config, provider down, template error) threw a 500 and left the approval action uncommitted from the caller's perspective even though the DB write had succeeded.

**Fix (`admin.py`):**
- Added `import logging` + `logger = logging.getLogger(__name__)`.
- `approve_user`: wrapped send in `try/except Exception as e` → `logger.warning("Approval email failed (non-fatal): %s", e)` + `email_status = "failed"`. DB write and 200 response always proceed.
- `reject_user`: same pattern.
- `create_invite`: already had a guard — added `logger.warning` so failures are visible in logs (was silently swallowed before).

Email failure now logs a warning and records `"failed"` in `email_logs` but never blocks the approval/rejection action.

141 pytest passing.

### 2026-04-15 Transactional email polish — approval, rejection, invite HTML templates

Completed in this pass:

**Change 1 — Approval notification email (`email_templates.py`, `admin.py`)**
- New `render_approval_html()` function: dark-themed, inline-CSS, table-based layout matching strategy report style.
- Header: logo (BRAND_LOGO_URL if set), dark card background, green accent line.
- Headline: "You've been approved — welcome to MacMarket".
- Body: guided workflow CTA copy (Analyze → Recommendation → Replay → Paper Order).
- CTA button: "Open the console" → `CONSOLE_URL`.
- Footer: "MacMarket · Invite-only private alpha · Questions? Reply to this email."
- `approve_user` route now passes `html=approval_html` to `EmailMessage`.

**Change 2 — Rejection / access-denied email (`email_templates.py`, `admin.py`)**
- New `render_rejection_html()` function: same structure, red accent line instead of green.
- Headline: "Account access update". Body: polite rejection copy with reply-to-admin instruction.
- `reject_user` route now passes `html=rejection_html` and updated subject/body.

**Change 3 — CONSOLE_URL env var (`config.py`, `.env.example`)**
- `console_url: str = "http://localhost:9500"` added to `Settings`.
- `.env.example` documents `CONSOLE_URL=http://localhost:9500` with comment.

141 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-15 Email logo URL config + Windows Task Scheduler runbook

Completed in this pass:

**Fix 1 — Email logo URL (`email_templates.py`, `config.py`, `.env.example`)**
- `_logo_img()` now checks `BRAND_LOGO_URL` env var first; falls back to embedded base64, then CSS text lockup.
- No broken image is ever rendered — the CSS lockup is always the final fallback.
- `BRAND_LOGO_URL` added to `Settings` in `config.py` with default pointing to GitHub raw asset.
- `.env.example` documents `BRAND_LOGO_URL` with the default GitHub URL so it works out of the box.

**Fix 2 — Windows Task Scheduler (`scripts/deploy_windows.bat`, `docs/private-alpha-operator-runbook.md`)**
- `deploy_windows.bat`: after servers start, checks for `MacMarket-StrategyScheduler` task and prints a `[WARN]` reminder if not registered.
- Runbook `Section 10` added: register/verify/check/remove schtask commands for the 15-minute strategy schedule runner.

141 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-15 Polygon.io live market data — wired and verified

Completed in this pass:

**Change 1 — `ProviderUnavailableError` exception class**
- Added `ProviderUnavailableError(Exception)` to `market_data.py` — raised by `PolygonMarketDataProvider` on HTTP errors, connection failures, and timeouts.
- `_request_json` split into `_fetch_url(url)` (handles raw URL, raises `ProviderUnavailableError`) + `_request_json(path, query)` (builds URL, delegates to `_fetch_url`).
- `ProviderUnavailableError` propagates through `MarketDataService.historical_bars`'s existing `except Exception` → falls back to demo data, triggering the 503 path in `_workflow_bars` when `POLYGON_ENABLED=true` and `WORKFLOW_DEMO_FALLBACK=false`.

**Change 2 — Pagination for `get_historical_bars`**
- After first Polygon response, follows `next_url` pagination (max 3 additional pages) until `limit` bars are collected.
- Slices to `[-limit:]` so the caller always receives exactly the requested number.

**Change 3 — Provider health probe: single snapshot call**
- `health_check` simplified from two API calls (`/v3/reference/tickers` + snapshot) to a single snapshot probe.
- Catches `ProviderUnavailableError` in addition to `HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError`.
- Status "ok" when snapshot succeeds; "warning" with failure detail otherwise.

**Change 4 — `.env.example` updated**
- Market data section now has a comment block explaining: Polygon as preferred provider, free tier note (delayed data sufficient for research), demo fallback opt-in, Alpaca as alternate scaffold.
- `POLYGON_API_KEY=your_polygon_api_key_here` (was blank before).

**Change 5 — `docs/local-development.md` enhanced**
- New "Live market data via Polygon.io" subsection with: setup steps, free tier signup URL, what changes in the UI (source chip, dashboard snapshot), and verification steps (`/admin/provider-health`, Analysis source chip).

No domain/recommendation/replay logic changed. 141 pytest passing (all run with `POLYGON_ENABLED=false` — no real API calls in test suite). `npx tsc --noEmit` clean.

### 2026-04-15 Options/crypto research preview surfacing

Completed in this pass:

**Change 1 — Market mode selector: explicit preview labels (`analysis/page.tsx`)**
- Option labels updated: "Options (research preview)" and "Crypto (research preview)"
- Preview notice block replaces bare StatusBadge: includes "Research preview" badge + full muted-text explanation paragraph
- Notice disappears when equities is selected

**Change 2 — Guided mode CTA disable (`analysis/page.tsx`)**
- "Create recommendation from setup" button disabled when `guidedMode && draftMarketMode !== "equities"`
- Inline disabled reason below button: "Guided workflow requires equities mode. Switch to equities to generate a recommendation."

**Change 3 — Recommendations page preview gate (`recommendations/page.tsx`)**
- Added `isPreviewMode = guidedState.marketMode === "options" || guidedState.marketMode === "crypto"` computed const
- Preview card shown when `isPreviewMode`: full copy + "← Restart in equities mode" link to `/analysis?guided=1`
- Queue table, active-rec hero, action row, detail grids, and chart all hidden when `isPreviewMode`
- Added `import Link from "next/link"`

**Change 4 — Dashboard modes callout (`dashboard/page.tsx`)**
- Dismissible `op-card` notice added after WorkflowBanner
- Copy: "Analysis supports equities (live), options, and crypto (research preview). Full workflow — replay and paper orders — is equities only."
- localStorage key `macmarket-preview-modes-noted` suppresses after first dismiss
- No new CSS — uses existing `op-card` + muted text styling

No backend changes. 141 pytest passing. `npx tsc --noEmit` clean.

### 2026-04-15 Operational readiness audit — Option B (second operator readiness)

Completed in this pass:

**Audit 1 — Deploy script currency: PASS**
- `scripts/deploy_windows.bat` verified current: `pip install -e ".[dev]"` matches `pyproject.toml`, uses `apply_schema_updates()` (not Alembic), ports 9510/9500 correct.

**Audit 2 — Runbook currency: UPDATED**
- `docs/private-alpha-operator-runbook.md` updated: title and all "Phase 1" references updated to "Phase 5/6".
- Section 3 (click-path verification) updated to include close-trade lifecycle, schedules, and guided flow details.
- Section 4 (private-alpha scope) updated to reflect Phase 5/6 reality.
- Section 6 (validation commands) updated with `npx tsc --noEmit` step.
- New **Section 8**: Clerk configuration requirements (environment config, not code).
- New **Section 9**: "Onboarding a second operator — checklist" (invite send, approval, first login, guided walkthrough, data isolation confirmation).

**Audit 3 — Invite flow: PASS (no code gaps)**
- `/sign-up` → Clerk SignUp renders ✅
- `/pending-approval` → correct copy ✅
- `/admin/pending-users` → admin-gated, shows approve/reject ✅
- Console layout gate: `pending` → `/pending-approval`, `rejected`/`suspended` → `/access-denied` ✅
- After approval, operator accesses console without re-login on next page load ✅
- Clerk config requirements documented in runbook section 8

**Audit 4 — Data isolation: ALL PASS**
All 7 user-scoped entities verified with `app_user_id` WHERE clause in backend queries:
- Recommendations ✅ · Replay runs ✅ · Orders ✅ · Paper positions ✅ · Paper trades ✅ · Onboarding status ✅ · Strategy schedules ✅

**Audit 5 — Empty states for brand-new operator: FIXED**
- Dashboard: "Recent replay runs" and "Recent orders" cards now show muted hint text with links when empty.
- Dashboard: "Pending admin actions" and "Alert / event log" show "No pending approvals." / "No active alerts." when empty.
- Replay runs table: empty tbody now shows a centered hint row ("No replay runs yet. Click 'Run replay now'…").
- Orders table: empty tbody now shows a centered hint row ("No paper orders yet. Click 'Stage paper order now'…").
- Schedules empty state already fixed in previous session — confirmed still good.

**Test counts after this pass:**
- Backend: 141 pytest tests passing (unchanged)
- `npx tsc --noEmit` clean (unchanged)

### 2026-04-15 Scheduled reports polish — output clarity + action links

Completed in this pass:

**Change 1 — Schedule list: last run outcome**
- `toRelativeTime()` helper added; schedule table "Last" column now shows relative time ("2 hours ago" / "Never run") using `latest_run_at ?? history[0].created_at` with `next_run_at` on the second line in muted text.
- "Latest summary" column replaced with a styled `StatusBadge`: green (`tone="good"`) when `top_candidate_count > 0`, amber (`tone="warn"`) when 0, "—" when never run.

**Change 2 — Run history rows: scannable summary**
- Run history row summary format changed from `top N / watch N / no-trade N` to `N top · N watch · N no-trade` (number-first, `·` separator).

**Change 3 — Candidate detail panel: guided workflow action link**
- Top candidates table: added "Action" column with `<Link>` styled as `op-btn op-btn-secondary` — "Analyze in guided mode →" linking to `/analysis?guided=1&symbol={symbol}&strategy={strategy}`.

**Change 4 — Empty state: first schedule guidance**
- Replaced generic empty state with: title "No scheduled reports yet", operator-useful description, and "Create your first schedule" CTA button that scrolls to the create form (via `createFormRef`).

No backend changes needed — `latest_run_at` and `latest_payload_summary.top_candidate_count` were already in the schedule list endpoint response.

`npx tsc --noEmit` clean. 141 backend pytest tests passing (no backend changes).

### 2026-04-15 Phase 6 — close-trade lifecycle (equities paper trading)

Completed in this pass:

**Backend: Change 1 — paper_positions lifecycle on order stage**
- `PaperPortfolioRepository.create_position()` added; called from `stage_order` when `order.side.value == "long"`.
- Creates a `paper_positions` row with `symbol`, `side`, `quantity`, `average_price`, `open_notional`, `status="open"`, scoped to `app_user_id`.

**Backend: Change 2 — explicit close position endpoint**
- `POST /user/orders/{order_id}/close` added to `admin.py`.
- Accepts `{ close_price: float }`. Finds order (scoped to user) and open position by symbol.
- Calculates `realized_pnl = (close_price - avg_entry) * quantity`.
- Creates `paper_trades` row; closes position (status="closed"); updates order status to "closed".
- Returns `{ order_id, symbol, realized_pnl, entry_price, close_price, shares }`.
- New repository methods: `get_open_position`, `close_position`, `create_trade` on `PaperPortfolioRepository`; `get_by_order_id`, `set_status` on `OrderRepository`.

**Backend: Change 3 — portfolio-summary endpoint wired to real data**
- Replaced stub return (`lifecycle_status: "scaffolded"`, stale notes) with `lifecycle_status: "active"`, `unrealized_pnl: null` (no live feed), `win_rate: null` when no closed trades.

**Frontend: Change 4 — Close position button on Orders page**
- "Close position" button (op-btn-destructive) shown in selected order detail panel when `status !== "closed"`.
- Click expands inline input pre-filled with limit_price + "Confirm close" / "Cancel" buttons.
- POST to `/api/user/orders/{orderId}/close`; on success stores result in `closeResults` map, reloads orders + portfolio summary.
- When `status === "closed"`: shows "Closed — P&L: +$X.XX" or "Closed — P&L: -$X.XX" in green/red.
- `closeInputVisible` resets when selected order changes.

**Frontend: Change 5 — Portfolio summary card redesigned**
- Card title: "Paper portfolio".
- `op-grid-4` layout: Open positions / Open notional / Realized P&L (colored) / Win rate (% or "—").
- Removed stub notes line. `PortfolioSummary` type updated: `unrealized_pnl: number | null`, `win_rate: number | null`.

**Frontend: Change 6 — Next.js API proxy route for close**
- `apps/web/app/api/user/orders/[orderId]/close/route.ts` created (POST proxy, same pattern as other workflow routes).

**Backend tests (4 new, 141 total):**
- `test_paper_order_stage_creates_open_position`: verifies PaperPositionModel row created after buy order.
- `test_close_position_calculates_realized_pnl`: verifies realized_pnl math + order status "closed".
- `test_portfolio_summary_reflects_closed_trades`: verifies summary endpoint returns lifecycle_status="active", unrealized_pnl=null, closed_trade_count >= 1.
- `test_win_rate_calculation`: one winner + one loser → win_rate between 0 and 1.

`npx tsc --noEmit` clean. 141 backend pytest tests passing.

Still open:
- Broader component-level frontend tests for guided hero variants.
- `atm_straddle_mid` expected-range method (Phase 6 scope).
- Full close-trade UI for existing closed orders without in-session closeResults (currently shows "Position closed" for DB-closed orders without local state).

### 2026-04-15 Strategy selector description + regime hints

Completed in this pass:

**Strategy description and regime hints on Analysis page**
- `StrategyRegistryEntry` Pydantic model extended with optional `description: str | None = None` and `regime_fit: str | None = None` fields (backend, no migration needed).
- All 6 equities strategies seeded with one-sentence descriptions and regime fit labels in `strategy_registry.py` (Event Continuation, Breakout/Prior-Day High, Pullback/Trend Continuation, Gap Follow-Through, Mean Reversion, HACO Context).
- `StrategyRegistryEntry` TypeScript type extended with `description?: string` and `regime_fit?: string` in `apps/web/lib/strategy-registry.ts`.
- `selectedStrategyEntry` useMemo added to Analysis page — derives the selected registry entry from `strategiesForDraftMode` and `draftStrategy`.
- Inline description block rendered below the Strategy `<select>`: description text + regime fit appended after a `·` separator, using muted text color (`var(--text-muted, #8b9cb3)`). Block only renders when registry data is loaded and the entry has a description.

`npx tsc --noEmit` clean. 137 backend pytest tests passing (no new tests — pure data extension of existing model).

Still open:
- Broader component-level frontend tests for all guided hero variants beyond current e2e coverage.

### 2026-04-15 Playwright e2e infrastructure — 8/8 tests passing

Completed in this pass:

**E2E test infrastructure fixes (playwright.config.ts, middleware.ts, layout.tsx)**
- Added E2E bypass check at the top of `clerkMiddleware` so the entire auth chain is skipped when `NEXT_PUBLIC_E2E_BYPASS_AUTH=true`.
- Added `isE2EAuthBypassEnabled()` early-return in `ConsoleLayout` so the server-side `await auth()` + redirect-to-sign-in path is never reached in test mode.
- Changed webServer port from 9500 to 9501 so Playwright always starts its own fresh dev server and never reuses a Clerk-keyed instance.
- Added `workers: 1` to the Playwright config — Next.js dev server cannot handle concurrent browser navigations reliably; serializing tests eliminates the ERR_ABORTED/ECONNRESET race.

**Broad API catch-all in `test.beforeEach` (both spec files)**
- Added `**/api/**` catch-all route that returns 404 for any unmocked API endpoint, registered before the specific `/api/user/me` mock and before all test-level mocks (last-registered wins, so individual test mocks still take priority).
- Eliminates ECONNRESET errors from Next.js proxying unmocked routes to the Python backend during parallel-capable test runs.

**`guided-workflow-hero.spec.ts` — 5 new guided-workflow tests (all passing)**
- Test 1 (guided /analysis): WorkflowBanner step states + TopbarContext guided hint.
- Test 2 (recommendations guided): queue collapsed by default, toggle expands table.
- Test 3 (replay guided empty state): no run yet, hero + "Run replay now" CTA.
- Test 4 (replay zero-fill): zero-fill message renders, equity curve suppressed.
- Test 5 (orders guided empty state): hero renders, stageability block when replay has no candidate.

**`phase1-closeout.spec.ts` — 3 tests stabilized (all passing)**
- Test 1 (analysis → recommendations → replay → orders click path): Removed fragile 401-counter flow (React StrictMode double-invokes effects in dev); simplified recommendations mock to always succeed; corrected button names ("Go to Replay step", "Go to Paper Order step") and labels ("recommendation:", "replay run:") to match actual non-guided DOM; added `has_stageable_candidate: true` to run list mock so the replay-page "Go to Paper Order step" button is enabled; fixed strict-mode violation on `getByText("ord-1")` → `{ exact: true }`.
- Tests 2–3 (dashboard/provider-health provider truth): selector fixes for exact badge matching and strict-mode-safe text assertions.

`npx tsc --noEmit` passes with zero errors. All 8 Playwright e2e tests pass (29s, 1 worker).

Still open:
- Broader component-level frontend tests for all guided hero variants remain open beyond current e2e coverage.

### 2026-04-15 Phase 5 — topbar context, role-gated sidebar, BUY/SELL badge, replay step border

Completed in this pass:

**Fix 1 — TopbarContext: dynamic topbar active-context line (topbar-context.tsx + console-shell.tsx)**
- Created `components/topbar-context.tsx` as a small client component wrapping `useSearchParams` in `<Suspense>`.
- Replaced the static "Workflow: Analyze → Recommendation → Replay → Paper Order" span in the topbar with `<TopbarContext />`.
- Display logic: guided + symbol → `SYMBOL · strategy`; guided + no symbol → "Guided workflow — start at Analyze"; not guided → "Explorer mode".

**Fix 2 — Role-conditional Admin sidebar section (console-shell.tsx)**
- Added `useState<string | null>(null)` for `appRole` and a `useEffect` fetch of `/api/user/me` on mount.
- Admin nav section is not rendered when `appRole !== "admin"` (renders null while role is loading, not a flash).

**Fix 3 — BUY/SELL side badge color (orders/page.tsx)**
- Replaced plain-text `{selected.side}` in the guided order detail hero and the "Selected order detail" panel with `<StatusBadge tone={... "buy" ? "good" : "warn"}>`.
- Table row already had this badge; detail panels now match.

**Fix 4 — Replay step row left-border by approval status (replay-runs/page.tsx)**
- Step row `div` now has `borderLeft: "3px solid #21c06e"` when approved, `"3px solid #f44336"` when rejected, `undefined` otherwise.
- Inline style only; no new CSS classes.

`npx tsc --noEmit` passes with zero errors.

Still open:
- Color-coded replay step rows already done (Fix 4 above). Playwright e2e coverage for guided hero cards, empty-state heroes, post-create hydration flows.
- Component-level frontend tests for guided hero variants.

### 2026-04-15 Phase 5 — save_alternative promote action + README Phase 5 milestone update

Completed in this pass:

**Backend: `save_alternative` action variant on promote route (`admin.py`)**
- `promote_queue_candidate` now reads `action = str(req.get("action") or "make_active")`.
- `action` is stored in `ranking_provenance` dict (persisted to recommendation payload) and returned in the response.
- Default behavior for existing callers is unchanged (`make_active`).

**Frontend: "Save as alternative" button fully wired (`recommendations/page.tsx`)**
- Added `saveAlt: false` to `loading` state object.
- Added `saveAlternative()` async function — same promote endpoint as `promoteSelected()`, but posts `action: "save_alternative"` and does NOT update guided lineage state (no `router.replace()`).
- Both "Save as alternative" buttons (guided Next action card + candidate detail panel) are now live: `disabled` and TODO comments removed, `onClick={() => void saveAlternative()}` wired, disabled while either `loading.promote` or `loading.saveAlt`.
- `promoteSelected()` now explicitly sends `action: "make_active"` in the request body.

**Backend unit test (`tests/test_recommendations_api.py`)**
- `test_user_ranked_queue_candidate_can_be_saved_as_alternative`: gets queue → POSTs promote with `action: save_alternative` → asserts `result["action"] == "save_alternative"` → fetches stored rec and confirms `ranking_provenance["action"] == "save_alternative"`.

**Sticky table headers on Replay + Orders history tables**
- Replay runs table: wrapper `maxHeight` set to 320px; all `thead th` elements get `position: sticky; top: 0; z-index: 1; background: var(--card-bg); border-bottom: 1px solid var(--table-border)` via inline styles.
- Orders table: wrapper `maxHeight` set to 280px; same sticky-th inline style pattern applied.

**README.md — Phase 5 milestone update**
- Changed stale "Phase 1 — Private alpha hardening" milestone reference in `## Current roadmap status and alpha milestone` to reflect current reality: "Phases 0–4 are complete. Current active scope is **Phase 5 — Operator console polish**."

Test counts: 137 pytest tests passing (up from 136). `npx tsc --noEmit` passes with zero errors.

Still open:
- Additional guided-mode visual polish (deeper hierarchy tuning for history tables/panels) — iterative.
- Broader component-level frontend tests for all guided hero variants (beyond current helper + e2e coverage).
- Playwright coverage for enhanced guided lineage hero cards and replay/order immediate post-create hydration.
- `atm_straddle_mid` expected-range method: contract-allowed, not yet emitted by preview logic.

### 2026-04-15 Phase 5 operator UI polish pass — banner chips, guided queue collapse, replay warning block

Completed in this pass:

**WorkflowBanner — human-readable context chips (workflow-banner.tsx)**
- Replaced individual `symbol: X`, `strategy: X`, `market: X` chips with a single composed primary context line: `SYMBOL · strategy · market mode`.
- Recommendation chip now reads `Rec #<id>` instead of `rec: <raw-id>`.
- Replay chip now reads `Replay #<id>` instead of `replay: <raw-id>`.
- Order chip now reads `Order #<id>` instead of `order: <raw-id>`.
- Source chip now reads `via <source>` instead of `source: <source>`.
- "lineage incomplete" chip now renders with amber text (`#f7b267`) and matching border, distinguishing it visually from neutral chips.

**Recommendations page — guided mode queue collapse (recommendations/page.tsx)**
- Added `showQueue` local state initialized to `!guidedState.guided` (collapsed in guided mode, expanded in explorer mode).
- In guided mode, queue table section defaults to collapsed and shows a single `op-btn-ghost` toggle: `View recommendation queue (N)` / `Hide recommendation queue`.
- Active-rec hero, workflow banner, and all other guided context remain at the top, unaffected.
- Explorer mode behavior unchanged — table renders expanded with no toggle.

**Replay page — styled stageability warning block (replay-runs/page.tsx)**
- Replaced the minimal inline text warning for `has_stageable_candidate === false` with a visible `op-error` card (existing class: `border: 1px dashed #7c4040; background: #2a1717`).
- Block shows: bold heading "Replay produced no stageable candidate", `stageable_reason` body (or default "No fills occurred or no recommendation met approval thresholds."), and muted operator note to return to Recommendations.
- Block only renders when `has_stageable_candidate === false`; `true` and `null`/`undefined` (older runs) are unaffected.

TypeScript: `npx tsc --noEmit` passes with zero errors after all three changes.

Still open:
- Additional guided-mode visual polish (including deeper hierarchy tuning for history tables/panels) remains iterative.
- Broader component-level frontend tests for all guided hero variants remain open beyond current helper + e2e coverage.

### 2026-04-15 replay/orders step-3/step-4 action-clarity + guided empty-state pass

Completed in this pass:
- Clarified navigation-vs-creation semantics in workflow CTAs:
  - navigation buttons now read **Go to Replay step** / **Go to Paper Order step**
  - creation buttons now read **Run replay now** / **Stage paper order now**
  - added explicit copy that arriving on Replay/Orders pages does not create artifacts.
- Reworked guided replay selection priority to strict lineage-first behavior:
  1) `replay_run` query param, 2) `source_recommendation_id`, 3) empty selection (no latest/symbol fallback in guided mode).
- Added guided replay empty-state hero for no-run-yet context with recommendation thesis + levels and single primary CTA (**Run replay now**).
- Reworked guided orders selection priority to strict lineage-first behavior:
  1) `order` query param, 2) `replay_run_id`, 3) `recommendation_id`, 4) empty selection (no latest fallback in guided mode).
- Added guided orders empty-state hero for no-order-yet context and single primary CTA (**Stage paper order now**).
- Promoted explicit lineage visibility on Replay/Orders via persistent workflow-lineage blocks showing recommendation -> replay run -> paper order.
- Improved replay post-create hydration:
  - hero/ticket state hydrates immediately from POST response
  - newly created run auto-selects
  - guided mode auto-expands first replay step
  - added explicit no-fill/no-approval message: “Replay completed, but no fills occurred. Portfolio remained unchanged.”
  - suppresses equity curve when equity path has fewer than two distinct values.
- Improved orders post-create hydration:
  - ticket hero hydrates immediately from POST response
  - new order auto-selects and detail panel scrolls into view
  - `router.replace` now uses fresh `sourceName` rather than stale source state.
- Added frontend shell build stamp (`build: ...`) so operators can confirm the active bundle.
- Added frontend selection-priority unit tests and updated Playwright workflow coverage for lineage sequence + zero-fill replay message behavior.

Still open:
- Additional guided-mode visual polish (including deeper hierarchy tuning for history tables/panels) remains iterative.
- Broader component-level frontend tests for all guided hero variants remain open beyond current helper + e2e coverage.

### 2026-04-15 guided single-active lineage + stageable-order gating pass (this pass)

Completed in this pass:
- Guided replay defaults to a single validation path when `guided=true` and no explicit `event_texts` are supplied.
- Replay runs now persist explicit stageability contract fields:
  - `has_stageable_candidate`
  - `stageable_recommendation_id`
  - `stageable_reason`
- Guided paper-order staging now enforces replay outcome gating:
  - blocks when replay produced no stageable candidate
  - stages from replay-approved recommendation lineage instead of stale query/source recommendation IDs.
- Analysis -> recommendation generation now threads strategy/timeframe/source metadata so persisted recommendations retain non-empty strategy context.
- Recommendations workspace now includes guided “Active recommendation” hero and practical table filters (symbol/strategy/status) with contained scroll region.
- Replay workspace table relabeled from `recs` to `paths`; guided CTA semantics distinguish navigation from creation and show stageability guardrails.
- Orders workspace language updated toward “Paper Orders / Order history”; added first paper portfolio summary endpoint + UI scaffold backed by new DB models.
- Added backend tests for:
  - analysis-generated recommendation strategy metadata persistence
  - guided replay single-path behavior
  - guided order-stage blocking when replay has no stageable candidate
  - guided order staging from replay-approved lineage.

Started early (foundation, not phase advance):
- Added `paper_positions` + `paper_trades` persistence scaffolding and `GET /user/orders/portfolio-summary` contract for future auditable close-trade lifecycle accounting.

Still open:
- “Save as alternative” explicit action is not yet separated from “Make active” in guided recommendations queue controls.
- Replay/Orders history tables still need sticky table headers + richer active-context toggles beyond current contained-scroll + lineage-first selection behavior.

### 2026-04-14 replay/orders lineage + guided coherence + sidebar layout pass (this pass)

Completed in this pass:
- Fixed console sidebar structure to render explicit vertical nav sections (`Workflow`, `Research`, `Reports`, `Admin`) and added overflow-safe main/content/header layout guards (`min-width: 0`, wrapping topbar title).
- Tightened guided Recommendations progression so replay CTA now requires a persisted recommendation in guided mode; queue promotion is the primary CTA until lineage is persisted.
- Added replay source-lineage persistence fields on `replay_runs` (source recommendation id, strategy, market mode, source, fallback mode) via Alembic migration and threaded those values through replay creation.
- Added shared backend lineage helper for extracting source strategy + key levels from persisted recommendation payloads.
- Added replay detail endpoint (`GET /user/replay-runs/{run_id}`) with source lineage, summary metrics, thesis, and key levels.
- Enriched replay steps endpoint payload with recommendation context fields (`rejection_reason`, thesis, levels, quality/confidence) while preserving per-step recommendation ids.
- Scoped replay detail/steps reads to the owning approved user and removed guided symbol fallback behavior (no silent AAPL fallback for guided replay/order prep).
- Updated guided Orders staging contract to require both `recommendation_id` and `replay_run_id` for auditable lineage.
- Added Next API proxy route for replay-run detail and updated Replay/Orders/Recommendations workflow surfaces to keep guided context threading and disable next-step actions when lineage is incomplete.

Still open:
- Additional guided-mode UX polish for fully collapsible secondary history tables on Replay/Orders remains iterative.
- Playwright coverage for the enhanced guided lineage hero cards and replay/order immediate post-create hydration remains open.

### 2026-04-13 guided-first-run + expected-range contract pass (this pass)

Completed in this pass:
- Onboarding completion checks are now user-scoped for replay/order milestones (no global completion leakage across operators).
- Added user-lineage persistence (`app_user_id`) for recommendations, replay runs, and orders, threaded through create paths and scoped listing routes.
- Dashboard now presents one canonical primary entry CTA: **Start guided paper trade** -> `/analysis?guided=1`.
- Guided analysis mode adds a visible step rail (**Analyze -> Recommendation -> Replay -> Paper Order**) and keeps advanced operator details behind an explicit toggle.
- Onboarding checklist moved out of Account and surfaced in Dashboard/guided workflow entry context.
- Added first-class options research-preview `expected_range` contract output on `/user/analysis/setup` (status + reason aware).
- Options expected move preview stays method-tagged and deterministic (`iv_1sigma`), explicitly separate from option structure/breakeven math.

Still open:
- `atm_straddle_mid` expected-range method is contract-allowed but not yet produced by live preview logic.
- Options/crypto recommendation promotion and downstream execution-prep remain explicitly blocked outside equities live-prep mode.

### 2026-04-13 guided continuity + strategy validation hardening (this pass)

Completed in this pass:
- `/user/analysis/setup` now returns explicit `400` validation when a supplied strategy label is not valid for the selected `market_mode`, including supported strategy display names in the error payload.
- Preserved default-first-strategy behavior only when no strategy query parameter is supplied.
- Added backend tests for invalid strategy/mode combinations and valid crypto strategy label resolution.
- Guided continuity state now threads across Analysis → Recommendations → Replay → Orders (`symbol`, `strategy`, `recommendation`, `replay_run`, `order`) via explicit guided query params.
- Added guided step rail + guided next-action cards on Recommendations, Replay, and Orders with one canonical CTA per page:
  - Recommendations: **Run replay**
  - Replay: **Stage paper order**
  - Orders: **Review staged paper order**
- In guided mode, advanced/operator detail defaults to collapsed state on Recommendations, Replay, and Orders.
- Recommendations guided UX now explicitly calls out that queue promotion is equities-only and that options/crypto currently stop at research preview.
- Expected move copy now explicitly states `iv_1sigma` as the current preview method, with tests for omitted-method behavior.
- Replaced FastAPI startup `on_event` with lifespan-based runtime validation.

Still open:
- `atm_straddle_mid` expected-range method remains contract-allowed but not yet emitted by preview logic.

### 2026-04-14 test stabilization + ops polish + UI fixes pass

Completed in this pass:

**Test suite stabilization (Pass 1)**
- Rewrote `tests/conftest.py` to use `StaticPool` in-memory SQLite engine (`sqlite://`) patched into `macmarket_trader.storage.db` before any route modules are imported.
- Root cause: file-based `macmarket_trader_test.db` with `engine.dispose()` caused intermittent "database is locked" / "no such table" errors on consecutive runs because module-level `TestClient(app)` singletons held pool connection references across test collection.
- StaticPool shares one connection so DDL (`drop_all`/`create_all`) never contends with pool connections; every test starts from a clean schema via `autouse` fixture.
- Removed redundant `setup_module()` / `init_db()` call in `test_auth_approval_api.py` that was superseded by the conftest fixture.
- Extended `ExpectedRange.method` Literal in `domain/schemas.py` to include `equity_realized_vol_1sigma`, `equity_atr_projection`, and `crypto_realized_vol_1sigma` — previously caused `ValidationError` in the full-operator e2e path.
- Result: 131 tests pass cleanly on three consecutive `pytest -q` runs with no flakes.

**Cloudflare Tunnel Windows service (Pass 2)**
- Created `scripts/start_cloudflare_tunnel.bat`: kills any existing `cloudflared.exe` processes, waits 2 seconds, then runs `cloudflared tunnel run macmarket-trader` in the foreground from `C:\cloudflared`.
- Added 4th task "MacMarket-Cloudflare-Tunnel" to `scripts/setup_task_scheduler.bat` using `ONLOGON` trigger (not ONSTART/SYSTEM) so cloudflared runs as the current user and can read `%USERPROFILE%\.cloudflared\` credentials.
- Working directory set to `C:\cloudflared` via PowerShell after task creation.

**Strategy-specific trade levels (Pass 3)**
- Rewrote equities section of `analysis_setup()` in `api/routes/admin.py` so each strategy family produces visually distinct entry zones, invalidation prices, targets, trigger text, and confidence values:
  - `breakout_prior_day_high`: entry at prior.high ± 0.1%, target = prior.high + 1–1.8× prior range, confidence=0.69
  - `pullback_trend_continuation`: entry near 7-day low, ATR-based stop, confidence=0.66
  - `gap_follow_through`: entry near open gap level, gap-up confidence=0.62 vs. flat=0.55
  - `mean_reversion`: entry below close (0.978–0.990×), target near 10-day mean, confidence=0.55
  - `haco_context`: entry near close ±0.3%, confidence=0.67
  - Default (event_continuation): entry just above close (1.001–1.007×), larger targets, confidence=0.71

**Equity realized-vol expected range (Pass 3)**
- Added `_build_equity_expected_range()` to `api/routes/admin.py`: computes log-return realized volatility from up to 20 recent daily closes, then `spot * annualized_vol * sqrt(horizon_trading_days / 252)` for the 5-trading-day horizon.
- Returns `status="omitted"` when fewer than 3 bars available; `status="blocked"` when realized vol is zero.
- Result: `/user/analysis/setup` now returns `expected_range` for equities instead of "preview unavailable."

**Email subject format (Pass 3)**
- Changed strategy report email subject from `"MacMarket · {schedule_name} · Apr 13 · 5 candidates"` to `"MacMarket · Apr 13 · Top: NVDA (0.93) + 4 more"` format, surfacing the top-ranked symbol and score directly in the subject line.

**Dashboard loading skeleton (Pass 3)**
- Added `const loading = !data && feedback.state === "loading"` sentinel to `dashboard/page.tsx`.
- All four stat cards (Account role, Approval, Provider summary, Last refresh) now show `"Loading..."` instead of `"-"` during initial data fetch.

Still open:
- `atm_straddle_mid` expected-range method remains contract-allowed but not yet emitted by preview logic.

### 2026-04-14 guided workflow banner + lineage hardening pass (this pass)

Completed in this pass:
- Added a shared workflow banner component across Dashboard, Analysis, Recommendations, Replay, and Orders with explicit step-state segmentation and selected-context strip.
- Added pathname-based active-route sidebar behavior and grouped IA sections: Workflow, Research, Reports, Admin.
- Unified core naming in console nav to Analyze, Recommendation, Replay, Paper Order; demoted non-core routes to supporting sections.
- Expanded guided continuity query contract to preserve `market_mode` and `source` in addition to symbol/strategy/lineage IDs.
- Removed silent first-load seed behavior on `/user/recommendations`, `/user/replay-runs`, and `/user/orders`; empty states are now honest.
- Hardened guided-mode execution-prep truth: options/crypto are blocked from replay/order progression with explicit 409 responses and UI explanation cards.
- `/user/recommendations/generate` now returns explicit `recommendation_id` field.
- Added replay/order lineage persistence foundations:
  - `replay_runs.recommendation_id`
  - `orders.replay_run_id`
  - replay and order create responses now include richer lineage summary fields.

Started early (foundation, not phase advance):
- Workflow banner styling and button variant primitives (`primary`, `secondary`, `ghost`, `destructive`) introduced for guided visual hierarchy.

## Core product pillars

### 1. Strategy Workbench
This is where an operator explores a symbol, selects a strategy, sees levels, overlays indicators, and decides whether a setup is actionable.

### 2. Recommendations Workspace
This is the flagship review surface for setups already born in analysis. It should answer:
- Why this symbol?
- Why this strategy?
- Why now?
- What are the levels?
- What next?

### 3. Replay Lab
This is the trust engine. It validates how the setup behaves path-by-path before paper execution.

### 4. Paper Orders
This is the disciplined execution prep layer, not just a dead blotter.

### 5. Scheduled Strategy Reports
This becomes one of the strongest product hooks:
- morning trade lineup
- strategy-specific ranked reports
- per-user recurring scans
- practical watchlist triage

### 6. Symbol Analyze
This is the fast “tell me what matters on this symbol now” page.
This should become your answer to generic technical-summary pages.

## Operator click path (tester quickstart)

1. Open `/analysis` and choose symbol/timeframe/strategy.
2. Click **Create recommendation from this setup**.
3. In `/recommendations`, review strategy/timeframe/levels/source and open replay.
4. In `/replay-runs`, run replay and verify approved/rejected step outcomes and source.
5. In `/orders`, stage paper order and confirm recommendation linkage + workflow source.
6. Use `/admin/provider-health` to confirm whether workflow ran on provider or explicit fallback.

## Short-term go-live phases

### Phase 1 — Private alpha hardening
Goal: internally usable and trustworthy for operator testing.

Must-have:
- stable auth
- stable recommendations → replay → paper orders flow
- provider/fallback truth clearly labeled
- clean identity/account/admin pages
- selectable indicators
- strategy workbench
- seeded/demo mode that still feels professional

## Phase 1 complete items

### 2026-04-03 pass notes

- Strategy Workbench (`/analysis`) is the primary setup entry and links into Recommendations.
- Core workflow surfaces exist and are connected: Recommendations -> Replay -> Orders.
- Workflow source labeling is explicit on core pages and fallback mode is visibly tagged.
- Same-origin workflow API access defaults to server-side session auth resolution with bearer fallback only.
- Inline action feedback is implemented (loading/success/error with retry) across core operator workflow pages.
- Admin users page and Account page present operator-facing identity/authorization fields (role, approval, MFA, last seen/authenticated, invite state when available).
- Provider health page includes operational impact language for fallback-vs-provider interpretation.

- Analysis now uses draft-vs-applied controls to prevent protected requests on every symbol keystroke.
- Analysis/recommendations chart indicator rendering is implemented for EMA 20/50/200, VWAP, Bollinger Bands, prior-day levels, volume bars, and RSI strip.
- Same-origin `/api/charts/haco` and `/api/user/analysis/setup` routes now return auth-initializing responses (425) instead of early 401 during token/session bridge timing.
- Provider-configured-but-degraded workflow blocks now include operator guidance for explicit local/dev demo fallback (`WORKFLOW_DEMO_FALLBACK=true`) without silent production fallback.
- Console/auth surfaces now use theme-aware MacMarket brand lockup and icon assets.
- Workflow pages (Analysis, Recommendations, Replay, Orders) now gate same-origin protected requests behind Clerk readiness and token-bridge fetch mode, reducing in-session 401/Invalid-token churn while auth settles.
- Core workflow tests now cover first-class indicator rendering output (EMA 20/50/200, VWAP, Bollinger, prior-day levels, volume, RSI) in chart overlay plumbing.
- App favicon now uses the square MacMarket icon asset (`app/icon.svg`) while sidebar lockup branding is scaled for operator-console readability.

### 2026-04-03 stability follow-up (this pass)

- Added a shared same-origin workflow proxy helper (`app/api/_utils/workflow-proxy.ts`) so protected Next API routes resolve auth once, preserve upstream status codes, and safely return JSON/text/empty upstream bodies without throwing opaque 500s.
- Routed core workflow endpoints (Recommendations, Replay, Orders, Analysis setup, HACO chart, Dashboard, Analyze) through the shared proxy path to surface upstream operator-usable detail (including 503/provider-blocked responses) instead of generic failures.
- Standardized same-origin workflow page fetches to session-mode `fetchWorkflowApi` on Analysis, Recommendations, Replay, and Orders, reducing client-token timing churn for signed-in operators.
- Cleared stale error banners on successful refresh paths and kept lightweight auto-clearing success feedback across core workflow pages.
- Analysis keeps draft/applied controls with explicit Refresh trigger; unsupported/non-renderable selected indicators are now surfaced as an explicit operator notice.
- Updated console branding treatment with larger lockup integration and topbar brand presence while keeping theme-aware lockup/icon assets.
- Kept work bounded to Phase 1 trust/stability hardening; broader end-to-end workflow coverage remains open below.

### 2026-04-03 identity reconciliation hardening (this pass)

- Fixed private-alpha auth sync reconciliation so split local identities (Clerk-sub row + invite/email row) merge into one canonical `app_users` row during login sync.
- Canonical merge now preserves local authorization truth (`approval_status`, `app_role`) and upgrades merged identity fields (`external_auth_user_id`, normalized email, best display name, MFA OR-merge).
- Added backend tests for invite/Clerk merge, placeholder-email reconciliation, approved/admin preservation, duplicate-row retirement, `/user/me` real-email output, and idempotent repeated login.
- Added one-time local/dev repair utility (`scripts/reconcile_duplicate_users.py`) for pre-existing duplicate rows.

### 2026-04-03 market-mode foundation (started early, bounded this pass)

Completed in this pass:
- Added first-class domain typing for `market_mode`, `instrument_type`, and `trading_session_model` plus typed multi-asset contracts (instrument identity, options contract/structure context, crypto market context).
- Added a centralized market-mode strategy registry and removed equity-only hardcoded strategy assumptions from analysis/analyze/schedule boundaries.
- Added options/crypto analysis research-preview payload behavior, including explicit non-live metadata and Iron Condor structure preview details.
- Added recommendation/replay guardrails so non-equity mode requests return explicit planned-preview responses instead of fake live success.
- Added schedule payload mode-awareness (`market_mode`) and explicit blocking for non-equity schedule execution in current Phase 1.
- Added analysis workbench market-mode selector + strategy filtering, with planned research preview labeling and guarded recommendation creation for non-equity modes.
- Added tests for enums/schemas/contracts, strategy registry coverage, analysis API market-mode behavior, schedule mode blocking, and frontend strategy filtering helper.

Still open from this track:
- Options and crypto replay semantics are not yet mode-native (still intentionally blocked for live generation in Phase 1).
- Options chain, IV surface/skew, and full Greeks provider integration remain later-phase items.
- Cross-mode `expected_range` / `expected_move` semantics remain roadmap-defined only until preview payloads, scoring logic, and replay annotations carry explicit method-tagged fields per mode.
- Crypto venue funding/basis/OI live data integration and liquidation-aware risk logic remain later-phase items.
- Full options/crypto paper execution routing is still out of scope for Phase 1.

### 2026-04-04 provider truth + HACO contract hardening (this pass)

- Unified provider truth model across Dashboard + Provider Health with explicit fields for:
  - configured provider
  - effective chart/snapshot read mode
  - workflow execution mode (`provider` / `demo_fallback` / `blocked`)
  - failure reason when probe fails.
- Provider health now reports blocked workflows (instead of false fallback-running copy) when provider degrades and `WORKFLOW_DEMO_FALLBACK=false`.
- Local/dev/test explicit demo fallback (`WORKFLOW_DEMO_FALLBACK=true`) is now messaged as explicit deterministic demo fallback execution mode.
- HACO Context indicator selector is now contract-accurate: only HACO/HACOLT are enabled and persisted; unsupported workflow overlays are not implied.
- Added backend tests for degraded-provider blocked-vs-demo-fallback messaging and frontend unit coverage for HACO indicator support contract.
- Updated local and market-data docs to match runtime workflow truth.

### 2026-04-04 workflow hardening + closeout validation pass (this pass)

- Added Phase 1 hardening regression coverage for:
  - deterministic Analysis/Recommendations/Replay/Orders coherence via user workflow API path,
  - recommendation-to-order lineage preservation using explicit `recommendation_id`,
  - dashboard/provider-health provider-truth-model agreement,
  - degraded-provider blocked-vs-demo-fallback workflow execution labeling.
- Hardened paper order staging contract:
  - `/user/orders` now supports staging directly from an existing recommendation id,
  - staged order now preserves recommendation linkage, symbol, and workflow source metadata from the originating recommendation when provided.
- Hardened same-origin admin provider-health route via shared workflow proxy helper so auth-initializing and upstream error handling match other protected workflow routes.
- Added practical operator runbook: `docs/private-alpha-operator-runbook.md` (local startup, workflow verification checklist, provider/fallback truth interpretation, and common recovery steps).

### 2026-04-04 Phase 1 closeout blocker pass (this pass)

- Added browser-level regression specs (Playwright) for:
  - full operator click-path flow: Analysis -> Recommendations -> Replay -> Orders,
  - stale-banner recovery in Recommendations after an initial auth/error response,
  - dashboard/provider-health rendered parity checks for shared provider-truth chips/messages.
- Added test-only auth bypass wiring (`NEXT_PUBLIC_E2E_BYPASS_AUTH=true`) for protected console pages used by browser automation, including admin provider-health page gate bypass in that test mode.
- Expanded auth/session-turnover integration coverage in frontend route utility tests:
  - Clerk token churn -> auth-initializing (`425`) behavior,
  - protected same-origin proxy status/body passthrough under upstream failures.
- Updated private-alpha runbook with explicit Windows PowerShell startup, seed, cache-clear, and verification commands alongside bash examples.

### 2026-04-04 verification environment closeout pass (this pass)

- Hardened pytest bootstrap to force deterministic test auth defaults regardless of developer `.env` drift:
  - `ENVIRONMENT=test`
  - `AUTH_PROVIDER=mock`
  - `EMAIL_PROVIDER=console`
- This restores `/user/me` mock-token provisioning flow for `user-token` and `admin-token` under pytest so `clerk_user` / `clerk_admin` seeding paths execute in tests.
- Clarified backend setup docs to match implementation truth: backend dependency install is `pip install -e \".[dev]\"` from `pyproject.toml`; no root `requirements.txt` is currently maintained.
- Hardened frontend verification guidance and startup behavior for Windows local validation:
  - explicit Node runtime requirement (`20.19.6`),
  - explicit warning to run outside OneDrive-synced directories for final `next build`/Playwright verification,
- Playwright `webServer` now clears stale `.next` before startup to reduce local cache/readlink brittleness.

### 2026-04-04 Phase 1 verification failure remediation pass (this pass)

- Hardened Analysis setup contract for non-equity preview modes:
  - `/user/analysis/setup` now returns deterministic planned-preview payloads for options/crypto without depending on provider-backed workflow bars,
  - avoids leaking provider-blocked `503` into preview-only market modes.
- Tightened workflow hardening regression fixture for recommendation->order lineage:
  - happy-path event seed now uses deterministic positive corporate-catalyst text,
  - test now asserts recommendation approval before staging order by `recommendation_id`.
- Stabilized Analysis Playwright click path selectors:
  - added stable test ids for the Analysis refresh and create-recommendation controls,
  - e2e now targets those stable controls instead of brittle copy-only selectors.
- Refactored dashboard/provider-health Playwright parity coverage:
  - default parity test now validates healthy provider mode (`provider` + `reads: provider`),
  - added explicit demo-fallback parity test under controlled mocked degraded fixture.

### 2026-04-04 Windows deployment validation + local runtime closeout (this pass)

- Verified deployed backend in `C:\Dashboard\MacMarket-Trader`:
  - `/health` returns 200
  - `pytest -q` passes (78 passed)
- Verified deployed frontend in `C:\Dashboard\MacMarket-Trader\apps\web`:
  - `npm test` passes (15 passed)
  - `npm run build` passes
  - manual `next start` succeeds locally
- Hardened Windows deployment script across:
  - robocopy exclusion fixes (`storage` / `data` package regressions)
  - backend startup launch path
  - backend health check reliability
  - Node 20.x tolerance messaging
- Confirmed deployed local DB bootstrap path (`macmarket_trader.db`) and local admin/user approval recovery path.
- Phase 1 is functionally complete for local private-alpha validation.
- Remaining follow-up is deployment/runtime auth/frontend startup polish, not core Phase 1 workflow correctness.
## Phase 1 remaining blockers (truthful)

- Execute the updated browser-level Playwright regression suite successfully in CI/runtime.
- Verify healthy-provider and demo-fallback dashboard/provider-health parity regressions are green in CI/runtime.
- Keep options/crypto paths in explicit research-preview mode until mode-native replay + risk + paper workflow parity is implemented and tested.

### 2026-04-04 gate-follow-up (this pass)

- Aligned provider-truth regression tests with the current configured/effective/workflow model:
  - `test_provider_health_result_structure` now pins a configured Polygon provider and asserts configured provider, effective read mode, and workflow execution mode explicitly.
  - `test_degraded_provider_reports_blocked_or_demo_fallback_explicitly` now uses a configured non-fallback provider in degraded mode so blocked-vs-demo-fallback assertions reflect real provider-truth policy.
- Fixed recommendation approval propagation in user workflow generation:
  - approved operators now deterministically propagate local `approval_status=approved` into recommendation approval state for `/user/recommendations/generate`,
  - added unit coverage for explicit approved-user override behavior so Phase 1 recommendation -> replay -> order lineage stays test-stable.
- Phase 1 remains open in this pass because full verification (`pytest -q`, `npm test`, `npm run build`, `npm run test:e2e`) could not be completed in this environment due missing Python dependency installation access (`httpx`/build dependencies unavailable from package index).

### Phase 2 — Alpha differentiators
Goal: become interesting enough that someone wants access.

Must-have:
- Symbol Analyze page
- ranked recommendation queue
- recurring scheduled strategy reports
- invite-only onboarding with useful admin tools
- polished chart overlays and indicator controls
- clear workflow feedback and action states

## Phase 2 started early (kept bounded)

These foundations stay in place but are not the focus until Phase 1 closes:

- Symbol Analyze workspace.
- Scheduled strategy reports (schedule CRUD + run-now + CLI due runner).
- Operator indicator registry/framework and persisted indicator preferences.
- Cross-mode `expected_range` / `expected_move` contract policy with explicit method tagging, horizon semantics, provenance, and blocked/omitted states.

### 2026-04-04 Phase 2 cohesive implementation pass (this pass)

Completed in this pass:
- Added a reusable deterministic ranking engine (`src/macmarket_trader/ranking_engine.py`) shared by:
  - Symbol Analyze
  - Recommendations ranked queue generation
  - Scheduled strategy reports
- Upgraded Recommendations into a backend-backed ranked queue workflow:
  - `/user/recommendations/queue` for deterministic candidate ranking,
  - `/user/recommendations/queue/promote` to promote a queue candidate into a stored recommendation.
- Upgraded Symbol Analyze to a triage-oriented output contract with:
  - mode/timeframe/source labels,
  - ranked strategy scoreboard,
  - operator next-action links into Analysis/Recommendations/Schedules.
- Extended scheduled strategy reports/listing payloads with:
  - run summary counts,
  - queue payload visibility,
  - schedule config summary + recent run summary metadata.
- Extended HACO workspace chart controls to include first-class workflow overlays on the price pane while preserving synced HACO/HACOLT strips.
- Added backend tests for ranking engine output, recommendation queue API, promotion flow, and schedule summary/detail behavior.

All remaining Phase 2 gaps closed in the 2026-04-12 closeout pass (see below).

Started early (bounded, carried into Phase 3):
- Ranking provenance payload structure is now rich enough to support later per-watchlist and multi-delivery expansion.

### 2026-04-12 Phase 2 closeout pass

Closed all five remaining Phase 2 gaps:

**Gap 1 — Recommendations page lineage UX**
- Added `getPromotedQueueKeys` helper to identify which ranked queue candidates are already promoted.
- Added queue summary strip to the Recommendations page showing pending / promoted / no-trade candidate counts at a glance.
- Implemented status tiers (promoted / staged / no-trade) with visual differentiation across the candidate list.
- Added promoted badges on queue candidates that already exist in the recommendation store.
- Added human-readable provenance panel explaining why each candidate was ranked (score breakdown, regime fit, strategy signal).
- Added contextual promote button that disables with tooltip when the candidate is already promoted.

**Gap 2 — Analyze triage provenance**
- Added `analyze-helpers.ts` with indicator provenance resolution and scenario label utilities.
- Surfaced indicator provenance text on Symbol Analyze so each indicator's contribution is explained per candidate.
- Added strategy-specific explainability text for all six strategy families (Event Continuation, Breakout, Pullback, Gap Follow-Through, Mean Reversion, HACO Context).
- Wired `reason_text` and `thesis` into scoreboard rows on the Analyze page.

**Gap 3 — Schedules editing controls + per-run drill-in**
- Added frequency, run_time, timezone, email_target, and top_n editing controls to the schedule form.
- Schedule form pre-populates all fields from the existing schedule record when editing.
- Made run history rows clickable, expanding to a full candidate detail panel for that run.
- Added backend `GET /strategy-schedules/{id}/runs/{runId}` endpoint returning the full candidate list for a specific run.

**Gap 4 — Admin invite / onboarding polish**
- Added “Action required” badge to the pending-users admin panel when unapproved invites are waiting.
- Added “Recent activity” card showing last five admin events (invites sent, approvals, rejections) with timestamps.
- Added empty-state guidance on the pending-users page when no pending users exist.

**Gap 5 — Frontend unit coverage**
- Added `analyze-helpers.test.ts` covering provenance resolution, strategy label helpers, and scoreboard formatting.
- Frontend test count grew from 28 to 48 tests (Vitest).

**Deploy fixes**
- Fixed DB wipe bug: `conftest.py` now uses per-test transaction rollback for isolation instead of dropping and re-creating the DB file between tests; `deploy_windows.bat` now guards `init_db` with an existence check so existing production DBs are never wiped on redeploy.
- Fixed frontend startup reliability: Next.js dev server now binds to `0.0.0.0` instead of `localhost` to avoid IPv6/IPv4 `TIME_WAIT` socket contention on Windows; health check URL pinned to `127.0.0.1`.

**Auth fixes**
- Added JWT verification leeway of 120 seconds to tolerate Clerk's 60-second session token window and local clock skew without spurious 401s.
- Removed Clerk session token customization (JWT template override) that was conflicting with the default token shape expected by the backend.
- Configured backend CORS origin and Clerk issuer URL to reference the dev host explicitly instead of relying on environment-inherited defaults.

### Phase 3 — Paid beta (complete)
Goal: something people would pay for as a research and trade-planning tool.

Must-have:
- multiple user watchlists
- per-user schedules
- email delivery + report history
- stronger provider support
- better replay visualization
- stronger ranking model
- onboarding and account quality
- operational logs and audit trail

## Phase 3 complete items

### 2026-04-12 Phase 3 implementation pass

- Added per-user watchlists with CRUD API and frontend management page.
- Per-user strategy schedules with frequency, timezone, run_time, email_target, and top_n editing controls.
- Email delivery with Resend adapter (`EMAIL_PROVIDER=resend`); console provider remains default for local dev.
- Strategy report run history persisted per schedule; per-run candidate detail drill-in via `GET /strategy-schedules/{id}/runs/{runId}`.
- Replay visualization: equity sparkline (SVG polyline over post-step equity), pass/fail summary bar, expandable per-step cards with pre/post snapshot JSON.
- Ranking model strengthened with score breakdown, regime fit scoring, and provenance labels surfaced in queue and detail panes.
- Onboarding status endpoint (`/user/onboarding-status`) tracking schedule, replay, and order completion milestones.
- Audit trail: dashboard `recent_audit_events` combining email logs, approval events, and schedule run events sorted by timestamp.
- 119 backend tests passing at Phase 3 close.

### Phase 4 — Vendor integrations (complete)
Goal: replace mock providers with vetted market/news/broker adapters; preserve all interfaces; keep research/live parity.

Must-have:
- replace mock providers with real adapters
- preserve the same interfaces
- keep research/live parity

## Phase 4 complete items

### 2026-04-12 Phase 4 implementation pass

- `PolygonNewsProvider` scaffolded: fetches headline articles by ticker via Polygon News API; falls back to mock on missing API key.
- `FredMacroCalendarProvider` scaffolded: fetches economic release calendar from FRED API; falls back to mock on missing API key.
- `AlpacaBrokerProvider` scaffolded: implements broker interface (order placement, status, cancel) against Alpaca paper-trading endpoint; falls back gracefully.
- Provider registry (`build_news_provider()`, `build_macro_calendar_provider()`, `build_broker_provider()`) wired in `registry.py`.
- News/macro/broker provider settings (`NEWS_PROVIDER`, `MACRO_CALENDAR_PROVIDER`, `BROKER_PROVIDER`) added to `config.py`.
- Auth → Clerk (`AUTH_PROVIDER=clerk`) and Email → Resend (`EMAIL_PROVIDER=resend`) already live from prior phases.
- Market data → Polygon (`POLYGON_ENABLED=true + POLYGON_API_KEY`) scaffolded and activatable via env vars.
- 119 backend tests passing at Phase 4 close.

### Phase 5 — Operator console polish (now active)
Goal: polished, operator-grade surfaces across all six console pages so the system is credible as a paid tool.

Must-have:
- recommendation explorer with chart level overlays (entry/stop/target price lines) and structured detail pane
- replay explorer with readable step snapshots and attribution summary
- order blotter with correct recommendation linkage and source-matched staging
- HACO workspace with richer signal narrative and thesis alignment annotation
- provider health with re-probe action and structured per-provider cards
- admin approval views with correct audit event source

## Long-term direction

### LLM role today
LLMs should:
- summarize catalysts
- explain setup selection
- generate bull/base/bear narratives
- classify news / event type
- provide operator-readable reasoning

### LLM role later
LLMs can progressively move into a larger seat, but only with guardrails:

#### Stage A — Explain
Summarize, classify, narrate.

#### Stage B — Rank assist
Help rank candidate setups using structured inputs and counter-thesis generation.

#### Stage C — Strategy orchestration
Suggest which strategy family should dominate under current regime.

#### Stage D — Supervised autonomy
Build a proposed morning trade lineup automatically for human approval.

#### Stage E — Execution co-pilot
Only after strong evidence, allow the system to stage paper flows or later supervised live flows.

## Product hooks / selling points

### Best near-term selling points
- Morning trade lineup email with ranked symbols and setups
- Explainable strategy workbench
- Replay before paper execution
- Event + regime context, not just indicator summaries
- Invite-only, operator-grade workflow

### Why this is stronger than generic broker features
Many platforms already offer technical summaries, chart studies, screeners, and alerts.
The edge for MacMarket-Trader should be integration and explanation:
- strategy + catalyst + regime + risk in one place
- ranked symbols, not endless noise
- explicit entry/invalidation/targets
- paper workflow connected to analysis
- recurring pre-market decision support

## What to avoid
- becoming just a charting app
- becoming just a signal spam app
- claiming autonomous “AI trading” before trust is earned
- open public signup too early
- mixing provider and fallback truth without clear labels

## What “good” should feel like
A trader should open the app and within 60 seconds know:
- which symbols matter today
- which strategy is active
- which setups are worth trading
- what levels matter
- what to ignore

## Multi-asset expansion policy

MacMarket-Trader remains **equities/ETFs-first** until Phase 1 trust and workflow hardening is complete.

However, the architecture should now treat **market mode** as a first-class concept so future expansion is not bolted on later.

Supported market modes:
- `equities` — current U.S. large-cap equities and sector ETFs
- `options` — structured options research and paper workflows
- `crypto` — crypto spot, then selected futures / perpetual-style research workflows

Design rule:
- every analysis request,
- every strategy selection,
- every replay run,
- every recommendation contract,
- every scheduled report,
- every paper-order intent,
- and every audit trail entry

must explicitly declare its `market_mode`.

The system must never assume that all strategies are equity strategies.

---

## Phase placement

### Current phase stance

**Do not move active development focus away from Phase 1.**

Options and crypto should begin as a **bounded foundation track started early**, not as a full product pivot during private-alpha hardening.

### Add under “Phase 2 started early (kept bounded)”

- Multi-asset market-mode foundation (`equities`, `options`, `crypto`) across request/response schemas, strategy registry, replay metadata, and audit payloads.
- Strategy registry refactor so supported strategies are keyed by market mode instead of scattered hardcoded lists.
- Analysis workbench market-mode selector with unsupported modes clearly labeled as research-preview / planned when full workflows are not yet enabled.
- Initial options strategy specifications, including **iron condor**, with contract structures, risk definitions, and research-only recommendation contracts.
- Cross-mode `expected_range` / `expected_move` policy with mode-aware methods, horizon typing, provenance, and explicit blocked/omitted handling instead of implied precision.
- Initial crypto strategy specifications for spot and later futures/perpetual-style contexts, with explicit handling for 24/7 session logic, funding, basis, and liquidation-aware risk fields.

---

## New roadmap section: Future market-mode expansion

### Cross-mode expected range / expected move policy

`expected_range` should be the normalized cross-mode research contract.
The UI may still say **expected move** where that is standard market language, especially in options workflows.

Purpose:
- provide volatility-aware range context for the intended decision horizon
- support entry/invalidation framing, strike placement, regime filtering, and replay annotations
- remain explicitly separate from targets, stop distances, payoff breakevens, liquidation thresholds, and sizing outputs

Any mode that exposes this concept should carry:
- method
- horizon value + horizon unit (`trading_days`, `calendar_days`, `hours`, or `expiration`)
- reference price type
- absolute move value
- percent move value when derivable
- lower bound
- upper bound
- snapshot timestamp
- provenance / input notes
- status (`computed`, `blocked`, `omitted`)
- blocked/omitted reason when applicable

Usage rules:
- never infer expected range from payoff breakevens, targets, stop distances, or liquidation thresholds
- never mix outputs from different methods without preserving the method tag
- block or omit the field when data quality is not strong enough
- treat it as range context, not as a probability guarantee

#### Equities / ETFs expected range policy

Use for the current 1 to 5 trading day swing horizon in regular-hours equities / ETF workflows.

Initial approved baseline:
- `equity_realized_vol_1sigma`: `spot_price * realized_vol_annualized * sqrt(horizon_trading_days / 252)`

Later / optional methods:
- `equity_atr_projection` (heuristic range context, not a sigma estimate)
- `equity_event_analog_range` (later, only after event replay/analog support is strong enough)

Equities caveats:
- carry `horizon_trading_days`, not DTE
- regular-hours session rules still apply; overnight gaps and scheduled events can dominate the estimate
- when earnings, macro, or company events are close enough to distort a baseline estimate, flag or block it rather than pretend normal-vol precision
- if an equities workflow uses listed-options data to estimate the underlying range, tag it explicitly as `options_implied_underlying_range` instead of merging it with equity-native methods

#### Options expected move policy

For options, the UI can continue to say **expected move** because that is the standard market term.
The stored contract should still remain method-tagged and explicitly separate from payoff math.

Initial approved methods:
- `iv_1sigma`: `underlying_price * implied_volatility * sqrt(DTE / 365)`
- `atm_straddle_mid`: `ATM call mid + ATM put mid`

Options caveats:
- expected move is range context for the underlying into the selected expiration; it is not the same thing as structure breakevens
- do not infer it from max profit / max loss / breakeven fields
- if bid/ask quality, open interest, or chain completeness is weak, block or omit it instead of fabricating precision

#### Crypto expected range policy

For crypto, use **expected range** as the default normalized term because 24/7 trading, venue fragmentation, and derivatives reference pricing make the simpler equities/options label less precise.
The UI can still map this to expected move where helpful, but the contract should stay explicit about reference price and horizon basis.

Initial approved baseline:
- `crypto_realized_vol_1sigma`: `reference_price * realized_vol_annualized * sqrt(horizon_calendar_days / 365)`

Later / optional methods:
- `crypto_atr_24x7_projection` (heuristic range context, not a sigma estimate)

Crypto caveats:
- always declare the price reference used (`spot_last`, `index_price`, or `mark_price`)
- for futures/perpetual-style research, prefer `index_price` or `mark_price` over thin venue last-trade prints when possible
- keep funding, basis, open interest, and liquidation stress adjacent but separate from the base range method in early implementations
- block or omit the field during dislocated venue conditions, thin liquidity, or unreliable reference pricing
- do not claim options-implied crypto expected move until crypto options are a separately supported mode with reliable chain data

### Options research mode

Goal:
Add a structured, explainable, research-first options workflow that uses deterministic strategy logic rather than “AI picks.”

Initial scope:
- defined-risk or fully specified multi-leg structures first
- chain-aware analysis
- implied volatility context
- expected move context for the underlying, kept separate from payoff math
- Greeks-aware scoring
- paper-only recommendation and replay support before any execution ambitions

Required data/logic concepts:
- underlying symbol
- expiration / DTE
- strike selection rules
- bid/ask and spread quality
- implied volatility level and percentile/rank when supported
- expected-move context with explicit method labeling
- skew / term structure hooks
- delta / gamma / theta / vega exposure
- open interest and volume per leg
- max profit / max loss / breakeven computation
- expected-move lower/upper bounds with snapshot timestamp and provenance
- assignment / early-exercise awareness where relevant
- contract multiplier and fees
- blocked / omitted handling when chain quality is not reliable enough for expected-move calculation

Initial options strategy family:
- **iron condor**
- bull call debit spread
- bear put debit spread
- bear call credit spread
- bull put credit spread

#### Iron condor specification

Research contract must include:
- underlying symbol
- expiration date / DTE
- short put strike
- long put strike
- short call strike
- long call strike
- net credit
- width of widest spread
- max loss
- lower breakeven
- upper breakeven
- expected-move method
- expected-move value
- expected-move lower bound
- expected-move upper bound
- short-strike distance versus expected-move envelope
- target profit rule
- stop / adjustment rule
- volatility entry filter
- event blocker flag (earnings, major macro, known catalyst)

Eligibility rules should prefer:
- range-bound underlying thesis
- elevated implied volatility / premium selling environment
- sufficient liquidity across all four legs
- acceptable bid/ask width and open interest
- short strikes evaluated explicitly versus the selected expected-move envelope instead of inferred from breakevens
- no nearby catalyst that can invalidate the range thesis

### Crypto research mode

Goal:
Add a crypto-native research track that respects 24/7 markets, venue fragmentation, leverage effects, and derivatives-specific behavior.

Rollout order:
1. crypto spot research
2. crypto futures / perpetual-style research
3. crypto paper-order support only after replay and audit parity are stable

Required data/logic concepts:
- venue / market identifier
- spot vs futures vs perpetual-style instrument type
- mark price vs index price where applicable
- expected-range context with explicit price-reference and horizon basis
- 24/7 session model and weekend handling
- funding rate history and extremes
- basis vs spot
- open interest
- liquidation / leverage stress context
- depth / spread / slippage estimates
- blocked / omitted handling when venue data quality is insufficient for range calculation
- news / on-chain or venue-event hooks when available

Initial crypto strategy family:
- crypto breakout continuation
- crypto pullback trend continuation
- basis carry monitor
- funding-extreme mean reversion monitor

---

## Acceptance criteria for the foundation pass

A valid early implementation should:
- keep current equities workflows working without regression
- add a first-class `market_mode` field across the main domain contracts
- centralize strategy definitions in a registry keyed by market mode
- define explicit method-tagged `expected_range` / `expected_move` semantics per market mode before surfacing them in scoring, preview payloads, or replay annotations
- expose options and crypto in the Analysis UI without pretending unsupported execution exists
- keep Recommendations / Replay / Orders honest about unsupported paths
- update README and roadmap text so repo intent matches code direction
- add tests proving the mode-aware registry and request contracts work

A valid early implementation should **not**:
- claim live options execution
- claim live crypto execution
- silently reuse equity sizing or replay logic for options/crypto
- silently reuse one mode's expected-range method as another mode's default
- infer expected range from payoff breakevens, targets, stop distances, or liquidation thresholds
- mix market modes in reports without explicit labels
- introduce fake precision when required chain/venue data is absent
- fabricate expected range when inputs are stale, weak, or missing
