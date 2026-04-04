# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-04-04

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
MacMarket-Trader is now executing **Phase 2 — Alpha differentiators** as the active implementation scope for this pass.
Phase 1 hardening remains an operational baseline, while this pass focused on Phase 2 workflow value delivery.

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

Remaining Phase 2 gaps (truthful):
- Recommendations page still needs deeper persisted recommendation + ranked queue side-by-side lineage UX polish.
- Analyze triage can be further improved with richer indicator scenario provenance and strategy-specific explainability text.
- Schedules page still needs finer-grained editing controls (frequency/timezone/email target) and per-run detail drill-in.
- Admin invite/onboarding surfaces still need stronger “recent activity + next action” operational guidance polish.
- Additional frontend unit coverage for new client-side queue/schedule state helpers remains open.

Started early (bounded, not Phase 3 complete):
- Ranking provenance payload structure is now rich enough to support later per-watchlist and multi-delivery expansion.

### Phase 3 — Paid beta
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
- Initial crypto strategy specifications for spot and later futures/perpetual-style contexts, with explicit handling for 24/7 session logic, funding, basis, and liquidation-aware risk fields.

---

## New roadmap section: Future market-mode expansion

### Options research mode

Goal:
Add a structured, explainable, research-first options workflow that uses deterministic strategy logic rather than “AI picks.”

Initial scope:
- defined-risk or fully specified multi-leg structures first
- chain-aware analysis
- implied volatility context
- Greeks-aware scoring
- paper-only recommendation and replay support before any execution ambitions

Required data/logic concepts:
- underlying symbol
- expiration / DTE
- strike selection rules
- bid/ask and spread quality
- implied volatility level and percentile/rank when supported
- skew / term structure hooks
- delta / gamma / theta / vega exposure
- open interest and volume per leg
- max profit / max loss / breakeven computation
- assignment / early-exercise awareness where relevant
- contract multiplier and fees

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
- target profit rule
- stop / adjustment rule
- volatility entry filter
- event blocker flag (earnings, major macro, known catalyst)

Eligibility rules should prefer:
- range-bound underlying thesis
- elevated implied volatility / premium selling environment
- sufficient liquidity across all four legs
- acceptable bid/ask width and open interest
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
- 24/7 session model and weekend handling
- funding rate history and extremes
- basis vs spot
- open interest
- liquidation / leverage stress context
- depth / spread / slippage estimates
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
- expose options and crypto in the Analysis UI without pretending unsupported execution exists
- keep Recommendations / Replay / Orders honest about unsupported paths
- update README and roadmap text so repo intent matches code direction
- add tests proving the mode-aware registry and request contracts work

A valid early implementation should **not**:
- claim live options execution
- claim live crypto execution
- silently reuse equity sizing or replay logic for options/crypto
- mix market modes in reports without explicit labels
- introduce fake precision when required chain/venue data is absent
- which symbols matter today
- which strategy is active
- which setups are worth trading
- what levels matter
- what to ignore
