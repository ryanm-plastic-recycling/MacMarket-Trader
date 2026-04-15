# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-04-15

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
MacMarket-Trader has completed **Phase 4 — Vendor integrations** and is entering **Phase 5 — Operator console polish** as the active implementation scope.
Phases 1–4 form the operational baseline. Phase 5 delivers the polished operator surfaces that make the system credible as a paid tool.

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
- Strategy selector enhancement: description + regime hint per entry from strategy-registry endpoint.
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
