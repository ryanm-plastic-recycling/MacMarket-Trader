# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-05-03

## 2026-05-03 Update - Options Data Provider-Health Sample Discovery
Options Data provider health now prefers a discovered Polygon/Massive sample
contract instead of relying first on a hardcoded option ticker. The readiness
probe asks for active SPY/AAPL option reference data, chooses a near-term
at/near-the-money contract when chain/reference access is available, retries a
small discovered candidate set, and reports the sample underlying, sample
option, and sample-selection method. The old static AAPL sample remains only as
a clearly labeled `static_sample` fallback when discovery returns no usable
active candidates.

If option reference discovery or option snapshots are blocked by provider plan
or permission, Provider Health reports the failure with sanitized, entitlement-
specific copy. This remains a readiness signal for paper Options Position
Review marks only and does not enable live trading, broker routing, automatic
exits, rolls, or adjustments.

## 2026-05-03 Update - Options DTE, Entitlement UX, Release Gate Progress, And Welcome Guide
Options research now uses a shared UTC-calendar DTE helper for displayed DTE
and Expected Range `calendar_days`. The fixed `2026-05-16` options research
expiration now evaluates to 13 DTE when assessed on `2026-05-03`, matching
Options Position Review and avoiding the stale 33-day expected-range horizon.
Frontend options research, Expected Range visualization, and durable paper
options lifecycle rows now prefer recomputed DTE from expiration/as-of when
available rather than trusting stale persisted DTE.

Options mark entitlement failures remain honest but less noisy. Repeated
Polygon/Massive "not entitled" option snapshot failures are aggregated at the
structure level while leg-level missing-data codes remain available. Provider
Health still reports `options_data` as degraded when the provider plan lacks
snapshot entitlement, and the UI states that option marks are unavailable
rather than fabricating P&L.

`scripts/run_release_gate.py` now prints progress before each major step,
records elapsed seconds per step in evidence, and supports `--quick` for scans,
targeted compliance/evidence tests, clean archive dry-run, and release
evidence generation without the full backend/frontend/TypeScript suite. The
Welcome Guide now starts with a compact MacMarket Quick Start cheat sheet and
documents current Provider Health, Market Risk Calendar, RTH chart, equity
paper, options paper, Options Position Review, option mark entitlement, and
release/evidence gate boundaries.

## 2026-05-03 Update - Options Expiration And Paper Settlement Review
Options Position Review now includes deterministic expiration, moneyness,
assignment-risk, exercise-risk, and paper settlement context for open options
paper structures. Each structure review exposes underlying mark metadata,
ITM/OTM summary, assignment/exercise summaries, expiration action summary,
settlement required/available flags, and a paper-only settlement preview when
an expired structure has a usable underlying mark. Each leg includes intrinsic
value, extrinsic value when a fresh option mark exists, moneyness,
distance-to-strike percentage, assignment risk, and exercise risk.

Expired open structures can be manually settled through
`POST /user/options/paper-structures/{position_id}/settle-expiration`. The
endpoint requires explicit `SETTLE` confirmation, is current-user scoped,
uses intrinsic values from the supplied or provider-backed underlying
settlement mark, persists through the existing options paper close path with
`settlement_mode=expiration`, and is idempotent through the existing
open-position guard. It does not create equity records, broker orders, live
exercise, live assignment, automatic exits, automatic rolls, or automatic
adjustments.

If the underlying mark is unavailable, expired structures are classified as
`settlement_blocked_missing_underlying` and settlement preview/confirmation
remain unavailable. Risk-calendar warnings still appear, but macro/event risk
does not trigger automatic close or settlement.

## 2026-05-03 Update - Provider-Backed Options Marks For Review
Options Position Review now uses provider-backed Polygon/Massive option
contract snapshots when available. The backend market-data service supports
`/v3/snapshot/options/{underlying}/{option}` lookups, caches snapshot reads,
and derives leg marks using deterministic precedence: valid bid/ask midpoint,
then valid latest trade, then prior/day close only as an explicitly stale
fallback, otherwise unavailable. Zero, null, stale, or permission-blocked data
is not treated as a live mark.

The options review endpoint now returns per-leg mark method, stale flag, IV,
open interest, provider-supplied Greeks, underlying price, source, as-of, and
missing-data context. When every required leg has a fresh provider mark, the
structure review computes current debit/credit, gross and net unrealized P&L,
estimated total commissions, return percentage, and mark-enabled
classifications such as `profitable_hold`, `max_profit_near`, and
`max_loss_near`. If any required leg mark is missing or stale, structure-level
P&L remains unavailable and the action stays `mark_unavailable`.

Provider Health now includes an `options_data` readiness entry that separates
configuration and probe state and states that options data readiness only
supports paper Options Position Review marks. It does not enable live trading,
broker routing, automatic exits, rolls, or adjustments. Orders now displays
option leg mark method, IV/OI, provider-supplied Greeks, structure mark, and
estimated P&L when available while preserving the review-only/no-routing
operator labels.

## 2026-05-03 Update - Options Position Review And Lifecycle Integrity Evidence
Options paper structures now have a review-only active position review layer
and a local lifecycle integrity audit without changing strategy math,
recommendation ranking, market-data behavior, paper equity lifecycle behavior,
broker routing, live trading, automated exits, automatic rolling, or automatic
adjustments. The backend now exposes
`GET /user/options/paper-structures/review`, with the Next.js proxy at
`GET /api/user/options/paper-structures/review`, returning one current-user
open options paper structure review per persisted structure.

The first implementation supports the existing paper options persistence branch
and defined-risk structures already accepted by the open/manual-close flow:
single long calls/puts, vertical debit spreads, and iron condors. The review
shape is structure/leg based rather than equity-position based. It includes
opening debit/credit, opening commissions, persisted payoff bounds,
breakevens, expiration/DTE status, risk-calendar context for the underlying,
leg details, missing-data flags, warnings, and deterministic action
classification. Provider-backed option leg marks are not yet available in the
current runtime, so the review returns `mark_unavailable` and explicitly lists
`option_mark_data` rather than fabricating marks or unrealized P&L.

Orders now includes an Options Position Review section next to Active Position
Review. It is labeled review-only, no automatic exits, no automatic rolling,
no broker routing, and paper position management. Regression coverage now
proves open options structures appear in review, closed structures are
excluded, cross-user review/close access is blocked, suspended users are
blocked, provider secrets are not exposed, manual close records gross/net P&L
and contract commissions without an x100 mistake, no orphan option records are
left behind, and equity paper sandbox reset leaves options records intact.

## 2026-05-03 Update - Phase 12 Model Validation And Performance Evidence Foundation
Phase 12 adds the first model-validation evidence layer without changing
strategy math, recommendation ranking, market-data behavior, paper lifecycle
behavior, broker routing, live trading, or automated exits. The new model
inventory documents setup engines, deterministic ranking/scoring, risk
sizing, Market Risk Calendar, Active Paper Position Review, LLM explanation
boundaries, and versioning gaps. A validation report template now defines the
expected objective, data period, universe, timeframes, provider/source,
session policy, baseline comparison, walk-forward method, replay method,
metrics, limitations, and signoff sections.

A read-only local validation script now writes
`.tmp/evidence/model-validation-YYYYMMDD-HHMMSS.json` and `.md`. It summarizes
stored deterministic recommendations, replay runs, paper trades, SPY/QQQ
baseline data when local `daily_bars` coverage exists, attribution by setup,
regime, catalyst type, timeframe, risk-calendar state, provider source, and
already-open vs fresh setup. Missing inputs are reported as `missing_data`;
the script does not fabricate performance and does not call LLMs, live market
providers, broker APIs, or order-routing paths.

This foundation is preliminary internal validation evidence only. Remaining
gaps include a dated point-in-time validation dataset, walk-forward split
definitions, benchmark capital assumptions, provider/source coverage reports,
independent benchmark review, model/rules version registers, drift monitoring,
and securities/legal review before any public or commercial performance
claims.

## 2026-05-03 Update - Phase 11B Operational Evidence Automation
Phase 11B operationalizes the compliance-readiness foundation into repeatable
local and CI-style evidence. Reusable scripts now scan for conflict markers,
scan for common secret patterns with redacted findings, verify clean release
artifact exclusions, and run a release gate that orchestrates scans, diff
hygiene, backend tests, frontend tests, TypeScript, npm audit report-only,
compliance-doc checks, clean-archive dry-run, release evidence generation,
and a runtime evidence manifest under `.tmp/evidence/`.

The release gate produces machine-readable JSON and Markdown reports and exits
nonzero on hard failures. Moderate `npm audit` findings remain report-only
unless the operator configures a stricter threshold; high/critical findings
fail by default. CI wiring was added for mock-provider, no-secret validation,
including backend/frontend tests, TypeScript, conflict/secret scans,
compliance tests, clean artifact dry-run, and CI-safe release-gate evidence.

Additional operational templates now cover evidence manifests, access
reviews, vendor reviews, and incident tabletop exercises. A Windows backup
schedule helper can print or, only with an explicit apply flag, register a
daily SQLite backup task. This pass remains documentation, scripts, tests,
and CI-style gating only; it does not change strategy math, recommendation
ranking, market-data behavior, paper lifecycle behavior, broker routing, live
trading, automated exits, or automatic scale-in.

Remaining manual governance includes assigning owners, reviewing generated
evidence before deploy, approving access/vendor/tabletop records, enabling and
monitoring backup schedules, retaining off-host backups, preserving monthly
restore-drill evidence, and obtaining legal/security/vendor reviews before
public or commercial expansion.

## 2026-05-03 Update - Phase 11 Trust, Compliance, And Acquisition Readiness Foundation
Phase 11 now has an evidence-first foundation for external diligence and
internal audit readiness. The new `docs/compliance/` evidence set covers the
control matrix, risk register, vendor inventory, data classification and
retention, incident response, change/release management, backup/restore and
DR, model risk management, regulatory boundary, and acquisition-readiness
checklists. These documents are framed as readiness artifacts only; they do
not claim SOC 2, ISO, regulatory, or legal certification.

Safe local evidence tooling was also added. SQLite backup and restore
verification scripts write sanitized reports under `.tmp/evidence/` while
using copies instead of overwriting the source database. A release evidence
generator collects git/runtime/dependency/test-placeholder/provider-config
metadata with secrets redacted, and a clean release archive generator excludes
local state, secrets, databases, logs, test artifacts, AI worktrees, and
generated build artifacts. Regression tests now verify required compliance
docs, regulatory-boundary wording, clean archive exclusions, release-evidence
redaction, and SQLite backup/restore copy behavior. This pass does not change
strategy math, recommendation ranking, market-data logic, paper lifecycle
behavior, broker routing, live trading, automated exits, or automatic
scale-in.

Remaining Phase 11 gaps are operational rather than foundational: named
owners, dated risk treatments, recurring backup jobs, off-host backup
retention evidence, monthly restore drill history, formal vendor/security
reviews, model/version registers, benchmark validation packets, incident
exercise evidence, and securities counsel review before any public or
commercial expansion.

## 2026-05-03 Update - Defensive Security Hardening Pass 2
The next defensive hardening slice landed app-local guardrails for Phase 1
alpha safety. Backend middleware now enforces practical in-memory abuse
limits on provider/LLM/workflow-heavy routes and validates Origin/Referer on
browser-originated mutating requests while preserving server-to-server/local
test calls without Origin headers. Backend payload handling now caps ranked
queue symbols/top_n/strategies, watchlist and schedule symbols, chart request
bars, recommendation/replay bars and text, Opportunity Intelligence selection
ids, and options replay/paper-leg payload sizes. Symbols are normalized to
uppercase and rejected when they fall outside the supported compact ticker
shape.

The web app now has centralized security headers in `next.config.ts`,
including `nosniff`, `DENY` frame protection, a strict referrer policy,
restricted browser permissions, and a report-only CSP that names Clerk
compatibility sources without enforcing a potentially disruptive policy yet.
Mutating `/api/*` requests also share the same safe Origin policy in Next
middleware. Production-like FastAPI app construction disables `/docs`,
`/redoc`, and `/openapi.json` by default, and admin invite APIs now return
masked invite tokens in admin payloads while preserving the emailed invite
link flow. HSTS remains an edge/deployment concern for Cloudflare/Caddy rather
than a Next app header in this pass.

## 2026-05-03 Update - Paper Equity Lifecycle Integrity Audit
A local/test-only lifecycle data-integrity audit now exercises the equity
paper workflow end to end: ranked queue generation, candidate promotion,
paper order stage/fill, fill-to-position lineage, Active Position Review
visibility, cross-user isolation checks, manual close, gross/net realized P&L
with commissions, portfolio-summary updates, closed-position exclusion from
Active Position Review, current-user paper sandbox reset, and preservation of
another user's paper records. The audit found no orphaned lifecycle rows in
the tested path and adds regression coverage rather than changing runtime
strategy math, recommendation ranking, sizing, market-data behavior, broker
routing, live trading, automated exits, or paper lifecycle semantics.

## 2026-05-03 Update - Defensive Security Audit
A defensive pre-alpha security audit reviewed README constraints, route/auth
inventory, user-scoping, secret/deploy hygiene, LLM boundaries, provider
health masking, browser security posture, and dependency audit output. The
audit found no high-confidence tracked secret values and confirmed deployment
mirroring excludes runtime env/state and local test/AI artifacts.

Low-risk authorization fixes landed from the audit: admin APIs now require
both local `app_role=admin` and `approval_status=approved`; recommendation
detail, approval, replay, paper-order staging, and fee-preview lookups are
current-user scoped; manual strategy-schedule run-now is owner-scoped; and the
Dashboard no longer exposes global counts, pending-user metadata, or recent
admin/email/schedule audit events to regular approved users. Provider Health
also has regression coverage proving configured secret values are not returned
in the health payload. This pass does not change recommendation ranking,
strategy math, sizing, market-data logic, LLM decision boundaries,
risk-calendar logic, paper order lifecycle semantics, broker routing, live
trading, automated exits, or automatic scale-in.

Remaining recommended security hardening is tracked as Phase 1 private-alpha
work: practical rate limits for provider/LLM-heavy endpoints, explicit
backend caps and symbol validation for bulk request payloads, app-level
security headers if not guaranteed by the edge proxy, a CSRF/origin policy for
same-origin mutating proxy routes, and planned dependency upgrades for the
moderate `npm audit` findings.

## 2026-05-03 Update - Browser Smoke Audit Fixes
A Playwright-driven local smoke audit ran against a disposable mock-auth
database with provider-backed Polygon reads enabled. The pass covered
Dashboard, HACO Context, Analysis, Recommendations, Orders, Settings, and
Provider Health across desktop, tablet, and mobile widths. It verified the
Recommendations symbol-input/workflow-button layout, ranked queue refresh,
risk-calendar badges, already-open paper-position badges, Opportunity
Intelligence comparison, Orders Active Position Review, paper sizing labels,
provider-health config/probe separation, and paper-only/no-live-routing copy.

Three small UI/testability fixes landed from the audit: HACO no longer crashes
when RSI is enabled because the RSI price scale is configured after the RSI
series creates that scale, the local E2E auth bypass no longer waits for
Clerk JS before protected workflow pages fetch data, and Active Position
Review no longer returns Unix-epoch mark timestamps as if they were real mark
times. This pass does not change recommendation ranking, strategy math,
market-data pricing logic, risk-calendar logic, LLM decision boundaries, paper
order lifecycle behavior, broker routing, live trading, automated exits, or
automatic scale-in.

## 2026-05-02 Update - Recommendations Layout And Mark-Age Cleanup
The Recommendations universe card now keeps the symbols input visually
dominant and moves workflow actions into a wrapping button row below it:
Refresh queue as secondary, Promote selected queue candidate as primary,
Replay as secondary, and Paper Order as primary/accent. Orders Active Position
Review now formats mark-as-of values through a mark-specific relative-time
helper that accepts ISO strings plus Unix seconds/milliseconds and fails closed
to `mark time unavailable` for missing, invalid, or epoch-like timestamps. This
is UI/display cleanup only; recommendation ranking, sizing, paper-order
staging, active review calculations, live trading, broker routing, automatic
exits, and automatic scale-in behavior are unchanged.

## 2026-05-02 Update - Already-Open Recommendation Awareness
Phase 7E active paper position management now extends into Recommendations and
the ranked queue. User-scoped recommendation list/detail responses, ranked
queue candidates, queue promotion responses, and generation responses attach
open equity paper position context when the same symbol is already open:
`already_open`, open position id/quantity/average entry, optional active review
classification/summary, and a review path back to Orders. This is response
decoration only; recommendation ranking, entry/stop/target/sizing math,
promotion, approval, replay, and paper-order creation behavior are unchanged.

Recommendations now badges already-held queue and persisted rows as `Already
open`, links to Active Position Review, and warns that additional paper orders
would increase exposure. Orders shows the same warning in guided paper-order
staging when a selected recommendation is already open, including existing/new
quantity and combined estimated notional when available. This remains
equity-only, review-only, paper-only, with no live trading, broker routing,
automatic close, automatic scale-in, or automatic order creation.

## 2026-05-02 Update - Provider Health Semantics
Provider Health now separates provider configuration from live probe results
with explicit `config_state` and `probe_state` fields. The operator UI no
longer treats "configured" as a live health signal: Polygon-backed market data
is healthy only when its probe succeeds, optional providers without live probes
are shown as configured/probe-unavailable, Alpaca readiness distinguishes
credentials from mock broker mode, and OpenAI LLM readiness distinguishes
probe skipped, probe failed, and probe OK without exposing secrets or changing
deterministic recommendation behavior.

## 2026-05-02 Update - Regular-Hours Intraday Normalization
Phase 3 market-data policy hardening now has an equity-only RTH normalization
path for provider-backed 1H/4H workflows. Polygon/Massive intraday requests use
30-minute source aggregates, filter bars outside 9:30 AM-4:00 PM America/New_York,
and locally re-aggregate canonical 1H and 4H regular-session buckets before
charting, Analysis, Recommendations, Opportunity Intelligence inputs, and
Market Risk Calendar data-quality checks consume the series.

The scope remains research/paper-only and does not add day trading, live
trading, broker routing, active paper position management, or LLM control over
entries/stops/targets/sizing/approval. Market Risk Calendar now treats
provider-session intraday bars in an RTH-required equity workflow as a
deterministic data-quality concern. See
`docs/rth-intraday-normalization-design.md`.

## 2026-05-01 Update - Phase 10R Started Early
Market Risk Calendar & Sit-Out Guardrails now have a deterministic,
paper-only risk gate with static/mock provider support, structured schemas for
scheduled events/evidence/decisions, config flags, macro/earnings/volatility
assessment tests, recommendation payload integration, paper-order staging
blocks/confirmation checks, Dashboard "Market Risk Today" context,
Recommendations risk badges, Orders calendar-risk confirmation UI, and
Opportunity Intelligence risk-context input.

LLMs may explain the risk context but cannot override the deterministic gate,
create unscanned candidates, alter sizing/levels/approval fields, route orders,
or enable live trading. Live macro calendars, earnings calendars, options
expected-move feeds, verified alternative-data sources, and full exchange
calendar integrations remain future provider work. See
`docs/market-risk-calendar-design.md`.

## Positioning
MacMarket-Trader is positioned as an invite-only, operator-grade trading
intelligence console — not "another charting page." The defensible edge is
strategy-aware analysis, event + regime context, explicit trade levels,
replay before paper execution, recurring ranked trade reports, and
explainable AI layered on top of deterministic logic. **It is paper-only.**

## Current Status
Phases 0–6 and Pass 4 complete. Three alpha users (admin + 2 approved).
Deployed at https://macmarket.io via Cloudflare Tunnel.
Tests: pytest 311 collected, vitest 206, Playwright 31, and tsc clean from
latest validation.
Phase 7 is complete for the current equity/paper-readiness foundation.
Phase 8C is complete for the current read-only, non-persisted options replay
preview scope.
Phase 8D is complete for the current paper-only manual-close options paper
lifecycle scope, including dedicated persistence, repository/service
contracts, open/manual-close behavior, contract-commission net P&L, frontend
operator UI, and closure audit/docs alignment.
Phase 8E1 is complete for the current operator risk-summary foundation on the
Recommendations options research surface.
Phase 8E2 is complete for the current Recommendations options provider/source,
as-of, and data-quality warning coverage.
Phase 8E3 is complete for the current guided Recommendations options workflow
UX.
Phase 8E is complete for the current Recommendations options risk/operator UX
surface only.
Post-8E smoke-test polish clarified reference-only chain-preview data
availability and Step 5 paper-close-result wording on Recommendations without
moving beyond the scoped paper-first options capability.
Phase 8F is complete, and Phase 8 is now closed for the current scoped
paper-first options capability only. Follow-on provider/source parity and the
Recommendations Expected Range visualization are now covered by the closed
Phase 9 current scope.
Phase 9A planning is complete for options operator parity and data-quality
hardening. Phase 9B is complete for durable paper-options Orders/Positions
visibility. Phase 9C is complete for the current provider/source/as-of parity
scope across Analysis, Recommendations, Orders durable paper-options rows,
Provider Health, and operator guidance using existing payload fields only.
Phase 9D is complete for the current Recommendations Expected Range
visualization scope. Analysis integration later landed in `10A1`; future
provider-depth, live routing, expiration settlement, assignment/exercise, and
probability modeling remain deferred. Phase 9 is closed for the current
options operator parity, source/as-of, and Expected Range visualization scope.
Phase 10 planning is now open as a deferred-work sequencing track. `10A1` is
complete for the frontend-only Analysis Expected Range visualization reuse,
and `10B1` is complete for frontend-only Orders display/readability polish on
durable paper-options lifecycle rows. `10C1` is complete for the first
frontend-only explainable metric UX foundation: central glossary registry,
reusable metric-help component, and narrow Settings / Expected Range /
Provider Health integrations. `10C2` is complete for compact Recommendations
score/risk-label help using the existing glossary and `MetricLabel`
component. `10C3` is complete for compact Orders P&L/commission label help
across equity Orders and durable paper-options rows. `10C4` is complete for
compact Analysis and Replay metric-label help. `10C5` is complete for the
closure audit, tiny safety-copy polish, and docs/test alignment, so the
explainable metric glossary/tooltips rollout is closed for the current
in-context scope. `10W1` through `10W8D` are complete for symbol/watchlist
design, current comma-entry workflow cleanup, schema/read-model planning, and
the additive symbol-universe schema/migration plus repository/resolver
foundation, current watchlist UI polish, and bulk symbol merge/duplicate
handling plus the recommendation/schedule universe-selection design checkpoint
and read-only resolved-universe preview API, Recommendations universe
selector/preview/apply UI, and Schedule static-snapshot universe
selector/preview/apply UI, followed by selector closure audit/docs/test
alignment.
Remaining Phase 10 slices stay open.
The track defines safe near-term options polish, medium-risk design
checkpoints, and explicitly later execution/crypto work without moving backend
runtime behavior. Future symbol discovery and watchlist management is now
tracked as a recommendation-universe workflow item, not trade execution or
broker routing; the design and schema/read-model checkpoints are now captured
in `docs/symbol-watchlist-design.md`, and the `10W4` schema foundation adds
only additive nullable tables without changing current watchlist JSON behavior,
schedule payload symbols, provider behavior, frontend UI, or recommendation
generation. The `10W5` repository/resolver foundation now reads those additive
tables internally without wiring production recommendation or schedule flows to
them, while `10W6` improves the current Schedules watchlist table using only
existing `watchlists.symbols` arrays and existing update/delete routes. `10W7`
adds client-side replace/merge handling and duplicate feedback for bulk pasted
symbols while preserving the same persisted arrays. `10W8` now documents how
future Recommendation and Schedule selectors should resolve manual, watchlist,
all-active, tags/groups, exclusions, and pinned symbols into the same current
symbol-array shape without changing runtime behavior. `10W8A` adds a protected
read-only preview route for that resolver output without submitting
Recommendations, mutating schedules/watchlists, calling providers, or changing
runtime recommendation/schedule behavior. `10W8B` adds the Recommendations
selector UI for previewing manual/watchlist/all-active universes and explicitly
copying resolved symbols into the existing manual input without changing queue
submit behavior. `10W8C` adds the Schedule selector UI for previewing and
copying resolved symbols into the existing schedule symbol input as a static
snapshot without changing schedule save payload shape or run behavior. `10W8D`
closes the current recommendation/schedule selector scope after audit and
validation, while provider-backed discovery, normalized production UI,
tags/groups, dynamic watchlist refresh, recommendation generation changes, and
schedule execution changes remain deferred.
Future operator glossary and explainable metric
tooltips are now tracked as workflow comprehension polish, not changes to
scoring, probability modeling, provider behavior, or execution semantics.
Phase 8 options hardening micro-pass preserved the scoped paper-only options
boundary and recorded that CLAUDE.md test context is now aligned to the
then-current frontend test count,
API-level iron condor open/close lifecycle coverage was added, expiration
settlement rejection coverage was added, the `opening_commissions`
reconstruction limitation was documented, and the dead `opening_commissions`
branch was removed without adding feature, schema, UI, replay,
recommendation, or brokerage behavior.
Active paper position management has now started as Phase 7E paper-only
lifecycle hardening before Alpaca paper integration. `GET
/user/paper-positions/review` and the frontend proxy `GET
/api/user/paper-positions/review` return one deterministic review object per
open equity paper position, and Orders now shows an Active Position Review
surface. This pass remains review-only: no live trading, broker routing,
automated exits, automatic closes, automatic scale-ins, options review, or
schema changes were added. The implementation follows
[`active-paper-position-management-design.md`](active-paper-position-management-design.md).
Intraday market-data correctness hardening is complete for the current
provider-backed chart/workflow path: aggregate-bar timestamps are preserved,
1H/4H HACO and workflow chart payloads emit unique intraday Unix-second chart
times, 1D payloads keep daily date values, chart routes no longer substitute
persisted daily bars for intraday requests, and Analysis / Recommendations
workflow bars now honor the selected timeframe. This remains paper-only and
does not add broker routing, live trading, or day-trading automation. Intraday
Polygon/Massive aggregate fetches now request newest bars first and locally
return the latest ascending provider window rather than the oldest slice of a
wide range. The follow-on RTH policy hardening is now started early and
implemented for equity 1H/4H workflows by fetching 30-minute source aggregates,
filtering provider-session bars to 9:30-16:00 ET, and re-aggregating local
regular-hours buckets.
Paper equity order sizing usability hardening is complete for the current
paper-only sandbox: recommendation sizing continues to use risk-at-stop, paper
order staging now applies an explicit per-user max-notional cap, optional
operator share overrides are bounded by deterministic recommendation size and
the notional cap, and current-user paper sandbox reset controls delete only
equity paper orders/fills/positions/trades while preserving recommendations,
replay runs, settings, watchlists, provider config, options-paper rows, and
paper-only/no-live-trading boundaries.
Safe LLM explanation-layer foundation is complete for the current
recommendation workflow: LLM providers are disabled by default, mock remains
the local/test default, optional real-provider calls are gated behind
`LLM_ENABLED`, provider output is schema-validated with deterministic fallback,
and persisted Recommendations can show an AI Explanation section that is
explicitly explanation-only. Deterministic engines still own entry, stop,
target, sizing, approval/no-trade status, and order routing.
Opportunity Intelligence is now started as a safe extension of that explanation
layer: selected stored recommendations can be compared in a market desk memo
using only backend-supplied deterministic candidate summaries, while
better-elsewhere references are limited to deterministic scan/stored
recommendation data. This remains research/paper-only and does not let the LLM
create trades, alter ranking, change approval, entry, stop, target, sizing, or
route orders.

## Completed Phases

### Phase 0 — Foundation
- Repo structure, FastAPI backend, Next.js 15 frontend, SQLite DB
- Clerk auth integration, local DB approval layer, audit logging
- `deploy_windows.bat` mirror + test pipeline + Windows Task Scheduler

### Phase 1 — Core workflow
- Analyze → Recommendation → Replay → Paper Order workflow
- Deterministic recommendation engine with explicit entry / stop / target levels
- Replay engine: historical bar walk, fill simulation, step logging, equity curve
- WorkflowBanner, guided mode, explorer mode, lineage threading via URL params

### Phase 2 — Identity + auth
- Invite-only onboarding, approval gate, role system (admin / user)
- Identity reconciliation: `invited::email` row → real Clerk sub on first sign-in
- Admin panel: pending users, invite create/resend/revoke, provider health
- Branded transactional emails (invite, approval, rejection) with inlined logo

### Phase 3 — Market data + providers
- Polygon market data integration (quotes, bars, news, options chain preview)
- Provider/fallback truth model with health indicators on dashboard + admin
- `WORKFLOW_DEMO_FALLBACK` for dev/demo deterministic-bar mode
- Index symbol normalization, `SymbolNotFoundError`, `DataNotEntitledError` handling

### Phase 4 — Recommendations + replay
- Recommendation queue with promote/make-active and save-as-alternative actions
- Replay validation gate: `has_stageable_candidate` blocks paper-order staging
- Strategy registry with regime-aware scoring + per-strategy hint copy
- Ranked queue → recommendation → replay → order lineage with full audit trail

### Phase 5 — Operator console polish
- Guided mode: sticky Active Trade banner, auto-advance CTAs, WorkflowBanner chips
- TopbarContext, strategy selector hints, role-conditional sidebar, brand pre-auth
- Pulsing primary CTA states ("Run replay now" → "Run again"), readable lineage
- Welcome guide page at `/welcome` rendered from `docs/alpha-user-welcome.md`
- 26 Playwright e2e tests gating guided workflow

### Phase 6 — Close-trade lifecycle + Pass 4
- Open positions list, inline close ticket, closed-trades blotter, realized P&L
- Cancel staged order, reopen closed position (5-minute undo window) + audit log
- `display_id` on recommendations (e.g. `AAPL-EVCONT-20260429-0830`) everywhere
  rec ID appears, with `Rec #shortid` fallback for legacy rows
- Per-user `risk_dollars_per_trade` override + Settings page at `/settings`
- Invite email with welcome-guide CTA + sign-in CTA (terse copy, two buttons)
- Timezone-aware schedule display ("08:30 AM ET — Indianapolis · 9:30 AM your time")
- 31 Playwright e2e gates, 99 frontend helper tests at Phase 6 close, 210 backend pytest gates

## Phase 7 Closeout + Upcoming Phases

### Phase 7A — Commission-aware realized paper P&L
- Complete for current equity/paper scope:
  `gross_pnl` / `net_pnl` split in `paper_trades`
- Complete for current equity/paper scope:
  per-trade equity commission (default `$0`) applied to realized paper close
  math
- Complete for current equity/paper scope:
  commission settings exposed in user Settings page
- Complete for current equity/paper scope:
  backend fields on `paper_trades` and per-user `commission_per_trade` /
  `commission_per_contract` on `app_users` with env fallback defaults
- Complete for current equity/paper scope:
  `realized_pnl` remains preserved as a back-compat alias to net P&L where
  legacy rows or older consumers still expect that field

### Phase 7B — Equity fee previews / projected net paper outcomes
- Complete for current equity/paper scope:
  replay / order / open-position operator surfaces show explicit equity-only
  fee estimates
- Complete for current equity/paper scope:
  projected net outcome is shown only when projected gross can be derived
  safely from existing recommendation levels
- Complete for current equity/paper scope:
  round-trip preview copy explicitly labels lifecycle estimates as `entry + exit`
- Complete for current equity/paper scope:
  close previews explicitly label fee estimates as `close-only`
- Complete for current equity/paper scope:
  unavailable projected gross/net values render as `Unavailable` rather than
  `0`, `NaN`, `undefined`, or `null`
- Note:
  current fee-preview math lives in `admin.py` for speed and reviewability;
  centralizing fee math into a dedicated module can happen in a later cleanup
  slice if Phase 7 grows further

### Phase 7C — Provider health + operator readiness
- Complete for current paper/provider-readiness scope:
  Admin / Provider Health now surfaces explicit Alpaca paper-provider
  readiness, including selected mode, configuration presence, and paper-only
  readiness framing without exposing secrets
- Complete for current paper/provider-readiness scope:
  FRED and news readiness now appear alongside existing auth, email, and
  market-data health so operators can verify macro/news context inputs
  explicitly
- Complete for current paper/provider-readiness scope:
  provider-health is framed as a pre-provider-expansion operator-readiness
  gate, not live-trading enablement
- Complete for current paper/provider-readiness scope:
  config-only providers clearly distinguish `Configured` from `OK` and show
  `Probe unavailable` when no dedicated safe live probe exists
- Note:
  FRED/news readiness is currently configuration-first and marks live probe
  status as unavailable where no dedicated safe lightweight probe exists yet
- Note:
  market-data workflow mode, fallback/blocking behavior, latency, and sample
  symbol remain the source-of-truth provider health contract for
  recommendation/replay/orders workflow trust

### Phase 7D — Closure criteria / remaining cleanup
- Complete for current equity/paper-readiness scope:
  roadmap/status wording has been cleaned up to match the implemented Phase 7
  slices without overstating live-provider or options support
- Complete for current equity/paper-readiness scope:
  provider-readiness language is clarified so config-only providers do not
  imply successful live upstream probe health
- Complete for current equity/paper-readiness scope:
  duplicate `.gitignore` cleanup is complete
- Complete for current equity/paper-readiness scope:
  Phase 7 test files are tracked and named clearly

### Phase 7E - Active paper position management
- Status:
  started for current equity paper lifecycle hardening. The backend review
  endpoint and Orders review surface are implemented for open equity paper
  positions only; options review remains deferred.
- Why before Alpaca paper integration:
  broker integration should not automate around an incomplete paper lifecycle.
  Before external paper brokerage plumbing is promoted, open paper equity
  positions need a deterministic mark-to-market review loop so the operator can
  manage existing exposure rather than seeing duplicate or confusing new-trade
  prompts.
- Completed in this pass:
  open equity paper positions are re-evaluated against current marks,
  recommendation/ranking lineage, stop/target distance, time stop, and market
  risk calendar state through `GET /user/paper-positions/review`.
- Target review model:
  one review object per open paper equity position with current mark price,
  unrealized P&L dollars, unrealized return percent, stop distance, target 1
  distance, target 2 distance, days held versus max holding days, current
  recommendation/ranking status for the same symbol, and an active position
  action classification.
- Position review statuses:
  `hold_valid`, `target_reached_hold`, `target_reached_take_profit`,
  `stop_triggered`, `time_stop_warning`, `time_stop_exit`,
  `scale_in_candidate`, `invalidated`, and `review_unavailable`, with stable
  precedence documented in the design file.
- Recommendation handling:
  implemented for current Recommendations and ranked queue surfaces. If a
  ranked recommendation or persisted recommendation symbol is already held in
  an open equity paper position, the backend attaches `already_open`,
  open-position id/quantity/average entry, optional active-review
  classification/summary, and an Orders review path. The operator surface shows
  `Already open` / `Review position` state instead of presenting the setup as a
  totally new trade by default.
- Scale-in guardrail:
  scale-in may be recommended only through explicit deterministic risk rules
  and must never silently average into a position without clear UI messaging
  and risk-limit feedback.
- Endpoint:
  `GET /api/user/paper-positions/review`, returning one review object per open
  equity paper position through protected frontend proxy to `GET
  /user/paper-positions/review`.
- Test expectations:
  open `GOOG` long returns current mark and unrealized P&L; near-stop positions
  return `stop_triggered` or warning status; above-target but still highly
  ranked positions return `target_reached_hold`; existing open symbols in
  ranked recommendations are flagged `already_open`; and scale-in candidates
  are blocked when portfolio risk limits are exceeded.
- Explicitly not included:
  live trading support, brokerage routing, real broker execution, automated
  close orders, automatic scale-in orders, schema changes, options position
  review, LLM position-review copy, or changes to existing paper order/replay
  behavior.

### Phase 7F - Paper equity order sizing usability + sandbox cleanup
- Complete for current equity/paper sandbox scope:
  `risk_dollars_per_trade` is clarified as risk budget at stop / max loss at
  invalidation, not a generic trade amount or max order notional.
- Complete for current equity/paper sandbox scope:
  per-user `paper_max_order_notional` is stored on `app_users`, exposed through
  `/user/me` and `/user/settings`, and defaults to `$1000` for private-alpha
  demo safety.
- Complete for current equity/paper sandbox scope:
  paper equity order staging preserves the original recommendation sizing while
  persisting/filling final shares after `risk_and_notional_capped` sizing.
- Complete for current equity/paper sandbox scope:
  optional `override_shares` may reduce the staged order but cannot exceed the
  deterministic recommendation shares, the max-notional cap, or existing
  recommendation/risk constraints.
- Complete for current equity/paper sandbox scope:
  Orders surfaces show recommended shares, editable order shares, estimated
  notional, risk at stop, max paper order value, cap-reduction warnings, and
  practical notional values on paper order/position/trade rows.
- Complete for current equity/paper sandbox scope:
  `POST /user/paper/reset` and the Orders testing tool reset only the current
  approved user's equity paper orders, fills, positions, and trades, with an
  audit log count summary.
- Explicitly not included:
  live trading support, broker routing, Alpaca implementation, Active Paper
  Position Management, deterministic entry/stop/target changes, recommendation
  sizing changes, options-paper deletion, or non-paper records cleanup.

### Phase 7 Closure Note
- Phase 7A through 7D are complete for the current equity/paper-readiness
  foundation.
- Phase 7E active-position management is started for open equity paper
  positions and remains the hardening gate before Alpaca paper integration.
- Remaining deferred items are intentionally moved to later phases and should
  not block Phase 8 planning.

### Phase 10L - Safe LLM explanation layer
- Complete for current workflow-comprehension scope:
  provider-agnostic LLM client contracts now cover event text summarization,
  event-field extraction, recommendation explanation, and counter-thesis
  generation.
- Complete for current workflow-comprehension scope:
  `LLM_ENABLED=false`, `LLM_PROVIDER=mock`, optional `LLM_MODEL`, and optional
  `LLM_API_KEY` keep local startup/tests free of required LLM credentials.
- Complete for current workflow-comprehension scope:
  malformed or unavailable provider output is rejected by structured schemas
  and replaced with deterministic mock explanation fallback.
- Complete for current workflow-comprehension scope:
  recommendation payloads store LLM provenance including provider, model,
  prompt version, generated timestamp, fallback status, and validation errors.
- Complete for current workflow-comprehension scope:
  Recommendations show an `AI Explanation` section labeled explanation-only,
  including counter-thesis/failure modes and explicit copy that deterministic
  engines own entry, stop, target, sizing, approval/no-trade status, and order
  routing.
- Explicitly not included:
  LLM trade selection, LLM entry/stop/target/sizing, LLM approval authority,
  broker routing, live trading, or brokerage execution.

### Phase 10M - Opportunity Intelligence
- Started for current workflow-comparison scope:
  `POST /user/recommendations/opportunity-intelligence` compares selected
  stored recommendations using structured deterministic candidate summaries
  and returns an explanation-only market desk memo.
- Complete for current safety scope:
  LLM output is schema-validated and rejected if it references candidate ids or
  symbols that were not supplied by backend-selected recommendation or
  deterministic better-elsewhere data.
- Complete for current local/test scope:
  mock/fallback output remains deterministic when `LLM_ENABLED=false`,
  provider output is malformed/unavailable, or a real-provider key is missing.
- Complete for current UI scope:
  Recommendations now includes an `Opportunity Intelligence` section where the
  operator selects two or more stored recommendations, requests a comparison,
  and sees best deterministic candidate, memo, comparison table,
  counter-thesis, deterministic better-elsewhere references, warnings, and
  missing-data notes.
- Explicitly not included:
  LLM-generated trades, LLM ranking changes, LLM approval changes, generated
  entries/stops/targets, sizing, order creation, live trading, brokerage
  routing, MCP server exposure, or browsing for unscanned symbols.

## Deferred From Phase 7

- `commission_per_contract` is stored and exposed, but options application is
  deferred to Phase 8 / options-fee parity work
- options-fee parity is deferred to Phase 8 / options
- broader fee modeling is deferred:
  per-share fees, regulatory fees, borrow / locate assumptions, and richer
  unrealized net P&L assumptions remain outside the current Phase 7 scope
- FRED/news dedicated safe live probes are deferred until later
  provider-depth work; current Phase 7 scope covers configuration/readiness
  visibility only
- Alpaca readiness remains paper/provider-readiness only, not live routing or
  brokerage enablement
- Active paper position management is now the required lifecycle hardening gate
  before Alpaca paper integration. Broker-paper plumbing should wait until open
  positions have mark-to-market review, already-open recommendation handling,
  and explicit scale-in risk guardrails.

### Phase 8 — Options research → paper parity
- Status:
  `8A` complete, `8B` complete for the current non-persisted research-only
  scope, `8C` complete for the current read-only, non-persisted
  replay-preview scope, `8D1` / `8D2` / `8D3` / `8D4` / `8D5` / `8D6` /
  `8D7` / `8D8` complete for design, schema, repository/service contracts,
  open/manual-close paper lifecycle behavior, contract-commission net-P&L
  modeling, frontend operator UI, and closure audit/docs alignment. `8E` and
  `8F` are now complete for the current scoped paper-first options capability. Dedicated
  options persistence tables, internal repository contracts, and open/manual
  close paper lifecycle paths now exist, the manual-close path now stores
  contract-commission-aware net P&L, and Recommendations now hosts a
  paper-only operator UI for open/manual-close workflows, while expiration
  settlement, broader provider/source parity across additional options
  surfaces, and execution-enablement changes remain deferred.
- Master plan:
  [options-architecture.md](options-architecture.md)
- Companion docs:
  [options-replay-design.md](options-replay-design.md),
  [options-paper-lifecycle-design.md](options-paper-lifecycle-design.md),
  [options-risk-ux-design.md](options-risk-ux-design.md),
  [options-test-plan.md](options-test-plan.md)
- 8A status:
  complete
- 8A acceptance:
  options scope, guardrails, repo anchors, and implementation sequence are
  documented without changing runtime behavior
- 8B status:
  complete for the current non-persisted research-visibility scope
- 8B acceptance:
  Analysis / Recommendations expose read-only options research safely, keep
  queue/promote/replay/order/staging CTAs suppressed, and render expected
  range, chain-preview, and missing-data states safely
- 8B not included:
  persisted options recommendations, options replay, options orders, options
  fills, options positions, and options trades
- 8C status:
  complete for the current read-only, non-persisted replay-preview scope
- 8C acceptance:
  supported defined-risk options structures can be previewed through
  deterministic expiration-payoff math plus a read-only operator UI, while
  equity replay behavior remains untouched and Expected Move / Expected Range
  stays contextual rather than modifying payoff math
- 8C implemented now:
  isolated pure payoff math helpers plus a dedicated read-only options replay
  preview contract at `POST /user/options/replay-preview`, with focused backend
  tests for long-option primitives, vertical debit spreads, iron condor,
  blocked invalid/naked-short payloads, explicit non-persistence, and a
  Recommendations-side operator payoff preview UI with compact summary and
  expiration payoff table; the surrounding options research preview continues
  to carry Expected Move / Expected Range context with safe blocked/omitted
  reasons and explicit research-only labeling
- 8C must not change:
  current equity `ReplayEngine`, equity replay persistence semantics, equity
  `RecommendationService.generate()` behavior, or equity order/fill semantics
- 8C not included:
  staged options orders, options positions/trades, mark-to-market parity,
  assignment/exercise automation, advanced Expected Move / Expected Range
  visualization beyond the current contextual summary, or live routing
- 8D status:
  `8D1` design checkpoint, `8D2` schema/migration foundation, `8D3`
  repository/service contracts, `8D4` open paper option structure behavior,
  `8D5` manual close paper option structure behavior, `8D6`
  `commission_per_contract` net-P&L modeling, `8D7` frontend operator UI,
  and `8D8` closure audit/docs alignment are complete for the current
  paper-only manual-close scope
- 8D acceptance target:
  supported defined-risk structures can move through an options-specific paper
  lifecycle with explicit leg summaries, contract-multiplier math,
  `commission_per_contract`, and gross/net realized P&L, without contaminating
  current equity paper lifecycle
- 8D implemented now:
  dedicated `paper_option_orders`, `paper_option_order_legs`,
  `paper_option_positions`, `paper_option_position_legs`,
  `paper_option_trades`, and `paper_option_trade_legs` tables now exist in ORM
  metadata and Alembic, with separate header/leg persistence, JSON
  breakevens, `execution_enabled=false` defaults on option paper orders, a
  `prepare_option_paper_structure(...)` validation helper, and an
  `OptionPaperRepository` for typed create/fetch contracts with focused schema
  plus repository tests; supported defined-risk structures can now open
  through a dedicated paper-only backend path at
  `POST /user/options/paper-structures/open`, which creates options-specific
  order and position headers plus legs without creating equity orders, replay
  runs, or recommendation rows and now exposes opening paper contract
  commissions; open positions can now close manually through
  `POST /user/options/paper-structures/{position_id}/close`, which writes
  options-specific trade headers plus legs, persists gross/net P&L plus
  total contract commissions, and keeps current equity write tables, routes,
  and replay/order behavior untouched; Recommendations now hosts a separate
  paper-only options lifecycle panel with same-origin open/close proxies,
  explicit commission-per-contract formula guidance, estimated opening/open +
  close commission visibility, in-memory manual close inputs/results for
  the newly opened position only, and closure-reviewed operator wording that
  keeps replay preview separate from persisted paper lifecycle actions
- 8D still deferred:
  expiration settlement mode; durable Orders visibility later landed in `9B`
  while broader provider/source parity remains future work
- 8D not included:
  naked short options, early partial fills, assignment/exercise automation, or
  live brokerage execution
- 8D manual smoke checklist:
  set `commission_per_contract` in Settings, open Recommendations in options
  mode, review research preview, run replay payoff preview, open paper
  option structure, manually close with per-leg exit premiums, verify
  gross/commission/net math, and confirm no live-trading language appears
- 8E status:
  `8E1` complete for the current Recommendations risk-summary foundation;
  `8E2` complete for the current Recommendations provider/source/as-of and
  data-quality warning scope; `8E3` complete for the current guided
  Recommendations workflow-clarity scope. `8E` is now closed for the current
  Recommendations options surface only.
- 8E acceptance target:
  operators can see strategy summary, legs, debit/credit, max profit/loss,
  breakevens, DTE/expiration, payoff context, warnings, provider/source
  labels, and Expected Move / Expected Range context without implying
  execution support
- 8E implemented now:
  Recommendations options research preview now includes a compact `Structure
  risk` surface that keeps research context, replay payoff preview, and the
  persisted paper lifecycle visually distinct while surfacing structure type,
  debit/credit, max profit/loss, breakevens, expiration / DTE, leg count,
  contract multiplier, Expected Range status/context, replay-preview status,
  paper lifecycle state, manual-close gross/net/commission outcome, and a
  compact caveat list that explicitly says Expected Range does not modify
  payoff math; the same surface now also shows workflow source, chain
  source/as-of, Expected Range provenance/as-of, safe `Source unavailable` /
  `As-of unavailable` copy, and provider-plan/payload warnings for missing
  chain, IV, Greeks, open interest, missing expiration/DTE, and SPX/NDX
  index-data caveats without implying execution approval; it now also adds a
  guided stepper for structure -> payoff preview -> paper save -> manual
  close -> paper-close result review, clearer paper-save wording that says no broker
  order is sent, explicit exit-premium instructions plus long/short hints,
  a stronger post-close result card, and lighter progressive disclosure so
  detailed provider/warning context stays available without overwhelming the
  operator; smoke-test polish now clarifies that the current chain preview is
  a lightweight reference snapshot, explains missing `last` / `volume`
  fields plus incomplete call-only or put-only chain sides safely, and labels
  the final guided step as the paper-close result rather than a generic saved
  result
- 8E not included:
  full chart-heavy payoff tooling, advanced Expected Move visualization in the
  first risk-UX slice, broader provider/source/as-of parity across additional
  options surfaces, or live-liquidity realism
- 8F status:
  complete for the current scoped paper-first options capability
- 8F acceptance target:
  supported options flows are coherent from research to replay to paper for the
  intended paper-only scope, tests are in place, deferred items remain
  explicit, and equity regressions stay green
- 8F implemented now:
  final closure audit confirms the current scoped options capability is
  complete: read-only research preview, read-only/non-persisted payoff
  preview, current paper-only open/manual-close lifecycle, commission-aware
  gross/net paper close results, and Recommendations risk/operator UX are all
  present and separately labeled without implying live routing, broker
  execution, expiration settlement, assignment/exercise automation, or other
  future options-parity work
- Phase 8 closure note:
  Phase 8 is complete for the current scoped paper-first options capability
  only. This does not imply advanced Expected Move visualization,
  provider/source/as-of parity across other options surfaces, expiration
  settlement, assignment/exercise automation, persisted options
  recommendations, options replay persistence, or live routing/execution.
- Phase 8 conservative sequence:
  `8C2.1` pure payoff math module and tests ->
  `8C2.2` vertical debit spread helpers/tests ->
  `8C2.3` iron condor helpers/tests ->
  `8C3.1` read-only replay preview contract ->
  `8C4.1` replay preview UI ->
  `8C5` replay tests/docs closure ->
  `8D1` schema/lifecycle design checkpoint ->
  `8D2` dedicated schema/migration foundation ->
  `8D3` repository/service contracts ->
  `8D4` open paper option structure ->
  `8D5` close paper option structure ->
  `8D6` contract commissions ->
  `8D7` operator UI ->
  `8D8` lifecycle tests/docs closure ->
  `8E` Recommendations options risk/operator UX closure ->
  `8F` closure review
- Phase 8 guardrails:
  options begin read-only, equity workflows must remain untouched unless
  explicitly tested, no live trading, no staged options orders until the
  correct phase, no schema until approved, no hidden execution semantics, no
  RecommendationService equity contamination, and no naked short support in
  early phases
- Phase 8 deferred items:
  persisted options recommendations, options replay persistence, staged options
  orders before runtime lifecycle slices, assignment/exercise automation,
  covered calls that depend on inventory modeling, mark-to-market /
  Greeks-driven valuation parity, advanced Expected Move visualization beyond
  the current contextual summary, and live routing remain outside the current
  implementation scope

### Phase 9 — Options operator parity and data-quality hardening
- Status:
  `9A` complete for planning; `9B` complete for the current durable paper
  options Orders/Positions visibility scope; `9C` complete for the current
  provider/source/as-of parity scope; `9D` complete for the current
  Recommendations Expected Range visualization scope
- Theme:
  durable operator visibility for current paper-first options plus consistent
  provider/data-quality framing, without adding live execution semantics
- 9A acceptance:
  scope, sequencing, safety boundaries, and explicit deferrals are documented
  for the post-Phase 8 options maturity pass
- 9B scope:
  options Orders/Positions dashboard parity
- 9B acceptance target:
  operators can see saved paper option positions and closed paper option
  trades outside Recommendations with clear paper-only labels, structure
  summaries, leg context, status, and gross/commission/net values where
  available, without contaminating current equity Orders behavior
- 9B implemented now:
  Orders now includes a dedicated `Paper Options Positions` section backed by
  a user-scoped `GET /user/options/paper-structures` contract and same-origin
  frontend proxy, showing open versus closed paper option lifecycle rows with
  status, timestamps, leg summaries, and gross/opening/closing/total/net
  paper results where available, while leaving existing equity Orders tables
  and actions unchanged
- 9C scope:
  provider/source/as-of parity across options surfaces
- 9C acceptance target:
  source/as-of context, reference-only chain caveats, incomplete call/put
  side warnings, and missing market-field handling are presented consistently
  across options research, payoff preview, paper lifecycle, and future durable
  operator surfaces
- 9C implemented now:
  Analysis options research now mirrors the existing Recommendations
  provider/source/as-of copy for Expected Range and chain preview fields where
  the setup payload already provides them; Orders durable paper-options rows now
  state that full provider/source metadata remains captured in research preview
  rather than persisted lifecycle rows; Provider Health adds options/index data
  caveats without implying execution enablement. No backend behavior, schema,
  lifecycle math, commission math, equity behavior, or UI actions changed.
- 9C closure:
  Complete for the current scoped options surfaces. Future provider-depth,
  deeper live probes, or new options-facing surfaces should reopen parity checks
  in their own phase rather than expanding this closure.
- 9D scope:
  Expected Move visualization
- 9D acceptance target:
  Expected Move remains research context only, gains clearer visualization
  only after durable operator visibility and provider/data-quality parity are
  stable, and still does not modify payoff math unless a later phase
  explicitly changes that contract
- 9D1 design checkpoint:
  complete; recommends a compact reusable horizontal range bar before any
  chart-heavy work, using existing `expected_range`, structure breakeven,
  max-profit/max-loss, expiration/DTE, and already-loaded replay payoff fields
  only. The visualization must show expected lower/upper bounds, optional
  current/reference price, breakeven markers, and muted unavailable/blocked
  states while saying Expected Range is research context only, does not change
  payoff math, and does not approve execution.
- 9D2 implemented now:
  a reusable frontend `ExpectedRangeVisualization` component renders a compact
  horizontal range bar from existing payload fields only and is integrated into
  the Recommendations `Structure risk` surface. It shows computed lower/upper
  bounds, reference-price context when derivable from the existing range,
  breakeven markers, expiration/DTE, max profit/loss labels, method/source/as-of
  and provenance text, blocked/unavailable states, and explicit research-only
  safety copy. Missing or invalid values render as `Unavailable` / `-` rather
  than `null`, `undefined`, `NaN`, or `Infinity`.
- 9D closure:
  complete for the current Recommendations Expected Range visualization scope.
  Closure audit tightened derived range-midpoint labeling so the component does
  not imply an actual current/reference price when the payload does not carry
  one, confirmed the component stays compact inside `Structure risk`, and kept
  Analysis integration optional/future.
- 9D not included:
  probability of profit, broker mark-to-market simulation, expiration
  settlement, assignment/exercise modeling, IV surface modeling, live
  execution decisions, provider probes, strategy scoring changes, or changes
  to options lifecycle, commission, equity, or recommendation-generation math
- Phase 9 implementation order:
  `9A` planning -> `9B` durable options Orders/Positions visibility
  complete -> `9C` provider/source/as-of parity complete for current scope ->
  `9D1` design checkpoint complete -> `9D2` reusable Expected Range
  visualization component plus first Recommendations integration complete ->
  `9D` closure audit complete for current Recommendations scope. Optional
  Analysis integration, richer replay/visual polish, and provider-depth work
  move to future phases only if explicitly reopened.
- Phase 9 closure:
  complete for the current options operator parity, provider/source/as-of, and
  Recommendations Expected Range visualization scope. No further explicit
  Phase 9 subphase is open unless future provider-depth or expanded options
  surfaces are intentionally reopened.
- Phase 9 not included:
  expiration settlement, assignment/exercise automation, persisted options
  recommendations, options replay persistence into equity replay flows, live
  routing/execution, broker integrations, or naked-short support

### Phase 10 - Deferred-work planning and safe options polish
- Status:
  planning started; `10A1`, `10B1`, `10C1` through `10C5`, and `10W1`
  through `10W8D` complete; broader `10A`, broader `10B`, optional
  glossary/reference-page work, provider search implementation, closure, and
  later subphases remain open
- Theme:
  organize remaining options/provider/crypto work into explicit risk bands and
  safe future slices before any higher-risk lifecycle, persistence, brokerage,
  probability, margin, or crypto implementation work begins
- Current safety posture:
  paper-first only; no live routing; no real brokerage execution; provider
  readiness does not equal execution enablement; Expected Range remains
  research context only; payoff preview does not equal a recommendation;
  options lifecycle remains paper-only; crypto remains future architecture /
  planning unless explicitly implemented later

#### Phase 10 deferred-work inventory and risk classification

Safe near-term:

- completed `10A1`: optional Analysis Expected Range visualization using the
  existing reusable component and existing setup payload fields only
- replay payoff visualization polish that remains read-only/non-persisted and
  does not change payoff math
- Orders dashboard polish for existing durable option positions/trades using
  already persisted fields only
- operator docs/training improvements and paper-only safety copy audits
- provider-health copy/readiness-only clarifications that do not add probes
- completed docs/design checkpoint for active paper position management as a
  paper-only lifecycle hardening gate before Alpaca paper integration
- docs/design checkpoint for symbol discovery and watchlist management as
  recommendation-universe workflow polish, before any schema or runtime changes
- completed `10W1`: symbol discovery and watchlist / recommendation-universe
  design checkpoint in `docs/symbol-watchlist-design.md`, preserving existing
  Phase 10 numbering where `10D` remains expiration settlement design
- completed `10W2`: frontend-only current comma-entry cleanup for
  Recommendations, Schedules, and current watchlist editing using shared
  manual parsing / parsed-preview helpers; no schema, provider search, storage
  replacement, or recommendation-generation behavior changed
- completed `10W3`: schema/read-model design checkpoint for a future
  user-scoped symbol universe plus watchlist membership model, compatibility
  snapshots, resolver behavior, migration/backfill strategy, and tests; no
  schema or runtime behavior changed
- completed `10W4`: additive symbol-universe schema/migration foundation with
  `user_symbol_universe` and `watchlist_symbols` models/tables, nullable
  provider metadata, duplicate constraints, indexes, and focused
  schema/migration tests; no frontend UI, provider search, current watchlist
  JSON behavior, schedule payload symbol behavior, recommendation generation,
  or schedule execution behavior changed
- completed `10W5`: backend-only `SymbolUniverseRepository` and
  `SymbolUniverseResolver` foundation for upserting/listing active user-symbol
  rows, normalized watchlist membership, snapshot-only membership, user-scoped
  reads, symbol normalization/dedupe, deterministic ordering, exclusions, and
  legacy watchlist JSON fallback; no frontend UI, provider search,
  recommendation generation, schedule execution, current watchlist JSON
  behavior, or schedule payload symbol behavior changed
- completed `10W6`: frontend-only current watchlist table/list polish on
  Schedules using existing `watchlists.symbols` JSON rows and existing
  watchlist create/update/delete routes; adds search, sort, symbol counts,
  normalized symbol chips, per-list symbol filtering, duplicate feedback,
  per-symbol removal through the current update route, ETF/index substitution
  guidance, and concise normalized-watchlist future copy without wiring
  provider search, normalized tables, recommendation generation, or schedule
  execution behavior
- completed `10W7`: frontend-only bulk symbol handling polish for current
  watchlist/symbol workflows; parser copy now covers comma/space/tab/new-line
  paste, previews show blank separators and duplicate feedback, watchlist edits
  have explicit replace versus add-to-existing modes, merge keeps existing
  symbols first and appends new unique pasted symbols, and existing `PUT`
  updates still submit the same deduped `symbols` array without provider
  search, normalized-table production UI, recommendation-generation, or
  schedule-execution changes
- completed `10W8`: docs-only recommendation/schedule universe-selection
  design checkpoint; records current raw symbol-array flows, future selector
  modes (`manual`, `watchlist`, `watchlist_plus_manual`, `all_active`,
  `tags`, `mixed`, exclusions, pinned symbols), schedule static-snapshot
  preference, optional dynamic-watchlist risk, resolver rules, future preview
  API implications, UX concepts, tests, and implementation slices without
  changing application code, schema, provider behavior, recommendation
  generation, or schedule execution
- completed `10W8A`: backend read-only resolved-universe preview API at
  `POST /user/symbol-universe/preview`; supports `manual`, `watchlist`,
  `watchlist_plus_manual`, `all_active`, and `mixed` preview modes using the
  existing resolver and user-scoped watchlist access, returns resolved symbols,
  counts, duplicate/exclusion/pinned/provenance metadata, and explicit
  preview-only/no-execution/no-recommendation-submit flags without provider
  calls, schema changes, schedule execution changes, watchlist mutation, or
  recommendation-generation changes
- completed `10W8B`: frontend Recommendations universe selector/preview/apply
  UI using the read-only preview API and existing watchlist list endpoint;
  supports manual, saved-watchlist, watchlist-plus-manual, and all-active
  preview modes, optional pinned/excluded symbols, resolved count/warning
  display, and an explicit `Use resolved symbols` button that copies the
  preview into the existing manual input without changing recommendation
  generation, queue submit behavior, provider calls, schema, or schedule
  execution
- completed `10W8C`: frontend Schedule universe static-snapshot
  selector/preview/apply UI using the same read-only preview API and existing
  watchlist list endpoint; supports manual, saved-watchlist,
  watchlist-plus-manual, and all-active preview modes, optional
  pinned/excluded symbols, resolved count/warning display, and an explicit
  `Use resolved symbols in this schedule` button that copies the preview into
  the existing schedule symbols field without saving until the existing
  `Create` or `Update selected` action is used; scheduled runs still use saved
  static `payload.symbols` snapshots and dynamic watchlist refresh remains
  deferred
- completed `10W8D`: closure audit for the current recommendation/schedule
  universe-selection scope; confirms the backend preview API is read-only,
  user-scoped, provider-free, and returns preview-only/no-execution/no-mutation
  flags; confirms Recommendations and Schedules are preview/apply only, keep
  existing submit/save paths explicit, preserve manual symbol entry and static
  schedule payload snapshots, and keep provider-backed discovery, normalized
  production UI, tags/groups, dynamic watchlist refresh, recommendation
  generation changes, and schedule execution changes deferred
- docs/design checkpoint for operator glossary and explainable metric tooltips
  before any shared component or registry work
- completed `10C1`: central glossary registry and reusable accessible
  metric-help component with narrow Settings, Expected Range, and Provider
  Health integrations
- completed `10C2`: Recommendations score/risk-label rollout for `Score`,
  `CONF` / confidence, `RR`, Expected Range, max profit/loss, breakevens,
  gross/net P&L, and options commission labels without changing scoring,
  lifecycle, payoff, commission, provider, schema, or execution behavior
- completed `10C3`: Orders P&L/commission label rollout for equity gross/net
  and fee labels plus durable paper-options max profit/loss, breakevens,
  gross/net P&L, opening/closing/total commissions, paper lifecycle, and leg
  P&L/commission labels without adding Orders actions or changing lifecycle,
  equity, commission, scoring, schema, provider, or execution behavior
- completed `10C4`: Analysis and Replay metric-label rollout for Analysis
  options risk/source labels and Replay score, confidence, gross/net P&L, and
  fee labels without changing recommendation scoring, replay behavior,
  lifecycle math, payoff math, commission math, schema, provider behavior, or
  execution semantics
- completed `10C5`: explainable metrics glossary closure audit for the current
  in-context scope, including tiny glossary safety-copy polish, focused tests,
  and docs alignment while keeping the optional glossary/reference page future
  work

Medium-risk:

- broader Orders dashboard parity if it needs new read-model joins or backend
  serialization, even without schema changes
- options replay/history integration design checkpoint because it touches
  future replay lineage and persistence semantics
- provider-depth/readiness probes if later implemented, because even safe
  probes can create paid-plan assumptions or imply execution readiness
- advanced Expected Move visualization beyond the current range bar if it
  introduces richer charting or interpretation language
- persisted options recommendations design, before implementation, because it
  must avoid `RecommendationService.generate()` drift and equity behavior
  changes
- symbol discovery and user-scoped watchlist implementation if it requires
  provider search calls, schedule/recommendation universe wiring, UI table
  workflows, or import flows
- active paper position management implementation because it touches open
  position marks, recommendation already-open state, stop/target/time-stop
  review, and scale-in risk guardrails even if it remains paper-only
- shared glossary registry and tooltip/popover implementation across Analysis,
  Recommendations, Replay, Orders, Settings, and Provider Health because it
  touches common UI primitives and app-wide wording consistency

High-risk:

- expiration settlement mode
- assignment/exercise automation
- partial fills for multi-leg option structures
- options replay persistence into replay runs
- persisted options recommendations implementation
- probability modeling / probability-of-profit
- margin modeling
- naked short support

Explicitly later / not now:

- live routing / broker execution / real brokerage execution
- crypto implementation or crypto paper execution
- naked short support, unless a later margin/risk program explicitly designs it
- assignment/exercise automation
- probability-of-profit as an execution or recommendation signal
- broad options order staging or brokerage order tickets
- treating discovered symbols, provider support labels, or options eligibility
  as execution approval
- describing `CONF`, `Score`, Expected Range, or replay/payoff outputs as
  probability of profit or execution approval without a separately designed
  and tested probability model

#### 10A - Options polish and operator workflow cleanup

- Type:
  frontend-only or docs-only first
- Complete when:
  optional Analysis Expected Range visualization, compact replay-payoff polish,
  or small operator-copy cleanup lands using existing payload fields only,
  with safe missing-value rendering and no backend behavior changes
- Explicitly not complete:
  replay persistence, options recommendations persistence, settlement,
  assignment/exercise, probability modeling, margin modeling, broker routing,
  or lifecycle math changes
- Must be tested:
  rendered source/as-of and unavailable states, research-only copy, no
  probability/execution/live-routing language, no `null` / `undefined` /
  `NaN` / `Infinity`
- Rollback/risk notes:
  hide or remove the frontend component/copy; no data migration or backend
  rollback should be required

First implementation slice:

- `10A1` optional Analysis Expected Range visualization. Reuse
  `ExpectedRangeVisualization` in Analysis options mode with existing
  `expected_range`, structure breakeven, expiration/DTE, source/as-of, and
  risk fields only. Keep it compact, read-only, and explicitly labeled as
  research context that does not change payoff math or approve execution.
- `10A1` status:
  complete for the current frontend-only slice. Analysis now reuses the
  existing Expected Range visualization component in options mode, including
  computed and unavailable expected-range states, without adding backend
  behavior, schema changes, provider probes, lifecycle actions, or payoff/math
  changes.

#### 10B - Orders dashboard parity for durable options rows

- Type:
  frontend-only first; backend read-model only if existing fields are
  insufficient and no schema change is needed
- Complete when:
  durable paper-options rows are easier to scan for open/closed state,
  expiration, DTE if derivable, legs, gross/opening/closing/total/net values,
  and source-metadata limitations without adding lifecycle actions
- `10B1` status:
  complete for the current frontend-only display/readability slice. Orders now
  labels durable paper-options rows as display-only paper lifecycle records,
  separates open paper positions from manually closed records, shows compact
  debit/credit, risk, commission, gross/net, status, and leg-detail tables
  from existing persisted lifecycle fields, and keeps provider/source/as-of
  limitations muted rather than error-like.
- Explicitly not complete:
  close/open actions from Orders, expiration settlement, partial fills, staged
  option orders, or brokerage routing
- Must be tested:
  open/closed row rendering, empty/loading/error states, safe unavailable
  values, durable metadata limitation copy, and equity Orders regression
- Rollback/risk notes:
  keep the dedicated options section removable without disturbing equity
  Orders tables

#### 10C1 - Operator glossary foundation

- Type:
  frontend-only shared foundation
- Complete when:
  a central glossary registry and reusable accessible metric-help component
  exist, the required initial terms are covered, and only low-risk surfaces are
  wired first
- Status:
  complete for the current first slice. `apps/web/lib/glossary.ts` now defines
  the initial terms, `MetricHelp` / `MetricLabel` provide compact
  click/tap/keyboard-accessible help, and Settings commission labels, Expected
  Range visualization labels, and Provider Health readiness context are wired
  without retrofitting the whole app.
- Explicitly not complete:
  broad Analysis, Recommendations tables, Replay, Orders, score columns,
  full glossary/reference page, probability modeling, provider probes,
  recommendation-generation changes, lifecycle behavior changes, payoff math
  changes, commission math changes, schema changes, live routing, or broker
  execution
- Must be tested:
  required registry terms, known/unknown `MetricHelp` rendering, commission
  guardrail copy, Expected Range research-only caveats, confidence/score
  non-probability wording, Provider readiness non-execution wording, and
  Settings integration
- Rollback/risk notes:
  remove the help icons/imports and leave the registry unused; no backend,
  data, or schema rollback should be required
- Note:
  this implements the glossary foundation slice requested as `10C1`; the
  separate options replay/history design checkpoint below remains open and is
  not closed by this work.

#### 10C - Options replay/history integration design checkpoint

- Type:
  docs-only first
- Complete when:
  a mode-native design exists for future options replay history and lineage,
  including whether options replay should have separate persistence rather than
  reusing equity `replay_runs`
- Explicitly not complete:
  options replay persistence, equity replay table changes, replay execution
  changes, or `RecommendationService.generate()` changes
- Must be tested later:
  no equity replay regressions, no persisted rows from read-only preview,
  explicit market-mode separation, and source/as-of continuity
- Rollback/risk notes:
  design-only checkpoint; do not implement until storage and UX boundaries are
  approved

#### 10D - Expiration settlement design checkpoint

- Type:
  docs-only first
- Complete when:
  the repo has a settlement-mode design covering required settlement price,
  expiration date checks, manual override/audit needs, long/short leg payoff at
  expiration, and explicit assignment/exercise exclusions
- Explicitly not complete:
  expiration settlement implementation, assignment/exercise automation, broker
  exercise actions, margin modeling, or naked short support
- Must be tested later:
  unsupported settlement rejection remains intact until implementation,
  settlement math fixtures, no double-close, user scoping, and equity
  lifecycle regression
- Rollback/risk notes:
  design-only checkpoint; implementation is high-risk and should require a
  separate approval pass

#### 10E - Provider-depth/readiness planning

- Type:
  docs-only first; later frontend/backend only if safe probes are explicitly
  approved
- Complete when:
  provider-depth gaps are listed without paid-plan assumptions and readiness
  copy remains clearly separated from execution enablement
- Explicitly not complete:
  new provider probes, paid-plan-specific claims, live routing, brokerage
  execution, or provider-based order approval
- Must be tested later:
  readiness-only copy, no execution implication, safe unavailable statuses,
  and no hidden provider/fallback mixing
- Rollback/risk notes:
  copy-only work is low risk; live probes are medium-risk and must be
  separately scoped

#### 10F - Crypto architecture planning only

- Type:
  docs-only
- Complete when:
  crypto mode requirements are documented separately from equities/options,
  including 24/7 sessions, spot/perpetual distinction, funding/basis context,
  provider assumptions, replay boundaries, and paper-only posture
- Explicitly not complete:
  crypto implementation, crypto provider wiring, crypto paper execution,
  crypto recommendations, or crypto UI actions
- Must be tested later:
  market-mode separation, no equities logic leakage, safe provider/fallback
  labels, and no execution implication
- Rollback/risk notes:
  planning-only; no runtime rollback

#### Future workflow polish - Symbol discovery and watchlist management

- Type:
  docs/design first; current frontend copy/preview cleanup is complete; later
  schema, provider, and user-workflow work only after explicit approval
- Status:
  `10W1` design checkpoint complete in
  [symbol-watchlist-design.md](symbol-watchlist-design.md). `10W2` current
  comma-entry cleanup is complete for the existing frontend manual-entry
  surfaces. `10W3` schema/read-model checkpoint is complete as docs-only
  planning for future normalized symbol-universe tables, membership records,
  resolver behavior, migration/backfill, compatibility, and rollback. `10W4`
  schema/migration foundation is complete for additive ORM models, Alembic
  tables, nullable provider metadata fields, indexes, uniqueness constraints,
  and focused backend tests. `10W5` repository/read-model and resolver
  foundation is complete for internal backend helpers only. `10W6` current
  watchlist table/list polish and `10W7` bulk merge/duplicate handling are
  complete for the existing frontend JSON watchlist workflow. `10W8`
  recommendation/schedule universe-selection design is complete as a docs-only
  checkpoint, `10W8A` read-only resolved-universe preview API is complete for
  backend preview-only use, `10W8B` Recommendations universe selector UI is
  complete for frontend preview/apply behavior, and `10W8C` Schedule universe
  selector UI is complete for frontend static-snapshot preview/apply behavior.
  `10W8D` selector closure audit is complete for the current scope.
  Existing Phase 10 numbering is preserved: `10D` remains the
  expiration-settlement design checkpoint, so symbol/watchlist work uses a
  workflow-polish `10W` lane unless the roadmap is explicitly renumbered later.
- Purpose:
  replace comma-only symbol entry and ad hoc operator memory with a user-scoped
  recommendation-universe workflow. This is symbol discovery and research
  universe management only, not trade execution, routing, or broker support.
- Current-state inventory:
  Analysis and Symbol Analyze use single-symbol free-text inputs;
  Recommendations and Schedules now show clearer manual-entry guidance and a
  parsed uppercase preview for comma/space/new-line input; schedules persist
  copied symbol arrays inside payloads; current watchlists are user-scoped rows
  with name plus `symbols` JSON and now show a searchable/sortable table,
  symbol counts, normalized chips, per-list symbol filtering, duplicate
  feedback, per-symbol removal through the existing update route, and explicit
  replace/add-to-existing edit modes for bulk pasted symbols; there is no
  provider-backed symbol search endpoint or production UI dependency on the
  normalized symbol-universe tables yet.
- Symbol discovery target:
  operators should eventually be able to search by ticker and company/security
  name; review ticker, name, asset type, exchange, provider/source support
  where available; distinguish equities, ETFs, indexes, options-eligible
  underlyings, and future crypto candidates where practical; and see ETF/index
  substitution guidance such as `SPX` / `NDX` versus `SPY` / `QQQ` without
  implying execution support.
- Watchlist target:
  replace raw comma-separated lists with searchable/sortable user-scoped
  watchlists that support add/delete of individual symbols, bulk add/import,
  duplicate handling, active/inactive status, optional tags/groups such as
  `Core`, `ETFs`, `Tech`, `Options Candidates`, and `Watch Only`, plus notes or
  source fields if useful.
- Recommendation-universe target:
  recommendation and scheduled-report workflows should eventually select from
  watchlists or groups rather than raw comma lists, while still allowing manual
  symbol entry when metadata is missing or provider lookup is unavailable.
  The `10W8` design says non-manual sources should show a resolved preview
  before submit, Recommendations should still submit a resolved `symbols` array
  unless a later contract is approved, and schedules should default to a static
  resolved snapshot rather than silently changing as watchlists change. `10W8B`
  implements the Recommendations side as preview/apply only: the operator must
  click `Use resolved symbols`, and queue refresh still uses the existing
  manual input pathway. `10W8C` implements the Schedule side as preview/apply
  only: the operator must click `Use resolved symbols in this schedule`, and
  create/update still saves the existing parsed `payload.symbols` snapshot.
  `10W8D` closes the current selector scope without changing recommendation or
  schedule runtime behavior.
- Recommended data-model path:
  use the compatibility-first `user_symbol_universe` plus `watchlist_symbols`
  foundation now added in `10W4`. Keep current `watchlists.symbols` snapshots and schedule
  payload symbols working while adding dedicated user-symbol universe /
  membership read models for duplicate handling, active/inactive state,
  tags/groups, notes, provider/source metadata, and schedule/recommendation
  universe resolution. The `10W5` resolver emits the same symbol-array shape
  current ranking paths already accept, but production recommendation and
  schedule flows are not wired to it yet.
- Guardrails:
  provider support labels must not imply live routing; missing metadata should
  not block manual symbol entry; options eligibility/provider coverage is
  research context, not execution approval; future crypto labels remain
  planning context until crypto is explicitly implemented; secrets and API keys
  stay out of docs and UI.
- Suggested implementation order:
  completed `10W1 design checkpoint` -> completed `10W2 current-state cleanup /
  comma-entry copy` -> completed `10W3 schema/read-model checkpoint` ->
  completed `10W4 schema/migration foundation` -> completed `10W5 repository/read-model
  and resolver` -> completed `10W6 current watchlist table UI polish` ->
  completed `10W7 bulk import/duplicate handling` -> completed `10W8 schedule/recommendation universe selection design` -> completed `10W8A resolved-universe preview helper/API` -> completed `10W8B Recommendations selector UI` -> completed `10W8C Schedule selector/snapshot behavior` -> completed `10W8D selector closure` -> `10W9
  provider-backed discovery only if separately approved` -> `10W10 closure`.
- Suggested next implementation slice:
  `10W9` provider-backed discovery design/implementation only if separately
  authorized. Keep provider-backed search, normalized table production UI,
  dynamic watchlist refresh, schedule execution changes, and ranking changes
  deferred until explicitly scoped.
- Explicitly not complete:
  normalized symbol-universe production UI, provider probes,
  provider search/fetch behavior, live routing, brokerage execution,
  recommendation generation changes, schedule
  execution changes, options execution approval, crypto implementation, or
  automatic strategy scoring changes.
- Must be tested later:
  schedule/recommendation selector compatibility, normalized symbol-universe
  production UI behavior, safe missing metadata rendering, no
  provider/live-routing implication, and no change to
  `RecommendationService.generate()` behavior.
- Rollback/risk notes:
  `10W2` is frontend-only and can be reverted by removing the shared parser /
  preview wiring. Later implementation should be split so watchlist UI can be
  disabled without affecting existing scheduled reports or recommendation
  generation.

#### Future workflow polish - Operator glossary and explainable metric tooltips

- Type:
  docs/design first; later frontend/shared-component work only after explicit
  approval
- Purpose:
  make MacMarket's operator terms, abbreviations, formulas, and caveats
  understandable in context without changing recommendation generation,
  scoring, provider behavior, lifecycle math, commission math, or execution
  boundaries.
- Target surfaces:
  Analysis, Recommendations, Replay, Orders, Settings, Provider Health, and
  future symbol/watchlist workflows should eventually use the same definitions
  for labels, table headers, cards, and form fields.
- Tooltip/popover target:
  small info icons beside important labels should open concise
  hover/click/tap popovers with plain-English definitions, formulas where
  applicable, short examples when useful, and caveats such as `not execution
  approval`, `not probability of profit`, or `not live broker data`.
- Shared glossary target:
  implement a central glossary registry when this becomes code, so terms stay
  consistent across the app and can optionally power a future glossary or
  reference page.
- `10C1` status:
  complete for the first foundation slice. The shared registry and reusable
  metric-help component now exist, with first integrations limited to Settings
  commission labels, Expected Range visualization labels, and Provider Health
  readiness context.
- `10C2` status:
  complete for the Recommendations score/risk-label rollout. Queue score,
  confidence, and RR labels plus options risk labels for Expected Range, max
  profit/loss, breakevens, gross/net P&L, and options commissions now use the
  shared glossary help component where the labels are most visible.
- `10C3` status:
  complete for the Orders P&L/commission-label rollout. Equity Orders summary,
  projected outcome, and closed-trade labels now use compact glossary help
  for gross/net P&L and equity fees, while durable paper-options rows expose
  help for max profit/loss, breakevens, gross/net P&L, options commissions,
  paper lifecycle, and leg P&L/commission labels.
- `10C4` status:
  complete for the Analysis and Replay metric-label rollout. Analysis now uses
  compact glossary help on options risk/source labels, and Replay now uses it
  on score, confidence, gross/net P&L, and fee labels where those labels are
  visible.
- `10C5` status:
  complete for the closure audit. Settings, Provider Health, Expected Range,
  Recommendations, Orders, Analysis, and Replay have current-scope in-context
  metric help on the highest-confusion labels; glossary safety wording remains
  explicit about no probability-of-profit, no broker execution, no live
  routing, no broker mark-to-market simulation, and unchanged payoff,
  commission, lifecycle, scoring, provider, and equity behavior.
- Initial term set:
  `RR` / risk-reward ratio, `CONF` / confidence, `Score`, Expected Range /
  Expected Move, `DTE`, `IV`, Open Interest, Breakeven, Max Profit, Max Loss,
  Gross P&L, Net P&L, equity commission per trade, options commission per
  contract, Provider readiness, Paper lifecycle, and Replay payoff preview.
- Design guidance:
  keep tooltips concise; send longer explanations to welcome/operator docs;
  avoid huge explanations in every table cell; support desktop hover plus
  keyboard, click, and touch behavior; keep visual weight low so the operator
  console stays dense and readable.
- Guardrails:
  `CONF` and `Score` must not be described as probability of profit unless a
  real probability model exists; Expected Range remains research context and
  does not change payoff math; Provider readiness does not imply live routing
  or execution; Paper lifecycle does not imply broker orders; commission copy
  must distinguish equity per-trade commissions from options per-contract
  commissions; secrets, API keys, and brokerage credentials stay out of docs
  and UI.
- Suggested implementation order:
  `glossary content/design checkpoint` -> `central glossary registry` ->
  `accessible InfoTooltip/MetricHelp component` -> `Settings and Provider
  Health low-risk labels` -> `Analysis and Recommendations score/risk labels`
  -> `Replay and Orders P&L/commission labels` -> `optional glossary page`.
  The Recommendations part of the score/risk-label step is complete in
  `10C2`; the Orders P&L/commission part is complete in `10C3`; the Analysis
  and Replay label rollout is complete in `10C4`; the current-scope closure
  audit is complete in `10C5`; optional glossary-page rollout remains future
  work.
- Explicitly not complete:
  probability modeling, recommendation scoring changes, provider probes, live
  routing, broker execution, commission math changes, payoff math changes,
  lifecycle behavior changes, schema changes, or broad UI redesign.
- Must be tested later:
  consistent definitions from the registry, keyboard/touch accessibility,
  concise rendering in dense tables/cards, no probability-of-profit wording for
  `CONF` or `Score`, Expected Range research-only copy, provider-readiness
  non-execution copy, and commission distinction between equity and options.
- Rollback/risk notes:
  design-only now; later UI work should be removable by hiding the help icons
  without changing underlying workflow data or behavior.

#### 10G - Phase 10 closure

- Type:
  review/docs/test closure
- Complete when:
  Phase 10 completed slices are documented, deferred items remain explicit,
  validation is green for touched surfaces, and no safety boundary has moved
- Explicitly not complete:
  live brokerage execution, real routing, expiration settlement,
  assignment/exercise, naked shorts, probability/margin modeling, persisted
  options recommendations, options replay persistence, or crypto implementation

### Later execution / implementation tracks - not active
- Alpaca paper integration:
  `BROKER_PROVIDER=alpaca`, real paper order placement, fill polling, account
  reconciliation, and broker execution semantics remain future work. Keys may
  be configured and scaffold may exist, but `BROKER_PROVIDER=mock` remains the
  current production setting. Active paper position management should land
  first so broker-paper integration does not automate an incomplete open
  position lifecycle.
- Crypto implementation:
  crypto-native strategy design and crypto paper execution remain later work
  after `10F` planning and explicit operator strategy decisions.

## Still Open (no phase assigned)

- `/account` page does not render Clerk `<UserProfile>` for self-service MFA
  enrollment (Clerk paid feature; admin enrollment via Clerk dashboard works)
- `MacMarket-Strategy-Reports` scheduled task may be redundant with
  `MacMarket-StrategyScheduler` — operator should verify and delete if duplicate
- `display_id` collision possible if two recs created for same symbol+strategy
  within the same minute — needs suffix handling
- npm audit: vitest/vite/esbuild moderate-severity dev-server vulns
  (GHSA-67mh-4wv8-2f99) — dev-only, deferred until vitest 4 migration
- `save_alternative` backend action variant not yet implemented (UI button
  exists, disabled)
- `atm_straddle_mid` expected-range method contract-allowed but not yet emitted
  by preview logic
- Brand logo CDN — currently using `apps/web/public/brand/` static; consider
  Cloudflare R2 / dedicated logo CDN for production scale
- Email delivery: end-to-end Resend verification for scheduled report delivery
  to a real inbox (logo URL configurable via `BRAND_LOGO_URL`, From display
  name via `BRAND_FROM_NAME`)
- HACO workspace: deeper indicator controls and signal visibility
- Analysis / Recommendations chart UX follow-up:
  HACO parity, Playwright hover/legend coverage, and advanced indicator
  settings remain deferred beyond the coordinated lower-panel pass
- Sticky table headers + richer active-context toggles on Replay / Orders
  history tables (beyond current contained-scroll + lineage-first selection)
- Active paper position management remains planned: open paper equity positions
  need current mark, unrealized P&L, stop/target/time-stop review,
  already-open recommendation handling, explicit scale-in risk guardrails, and a
  future read-only `GET /api/user/paper-positions/review` contract before
  Alpaca paper integration.
- Alpha smoke cleanup note:
  LLM provider health, queue-level Opportunity Intelligence inputs, and ranked
  queue risk-calendar badges are now the immediate usability hardening layer.
  Active Paper Position Review remains the next implementation phase; the
  `GET /api/user/paper-positions/review` contract is still docs-only and should
  not be linked in the UI until implemented.
- Options/crypto live execution semantics — current options support is still
  paper-first only (research preview, read-only payoff preview, and
  paper-only lifecycle plus durable Orders visibility). Current provider and
  data-quality parity is closed under Phase 9; deeper provider-depth work,
  crypto implementation, and live execution remain deferred. Phase 10 now
  organizes these items into planning/polish/design slices before any runtime
  expansion.
- Symbol discovery and watchlist management — current symbol entry and
  scheduled-report watchlists remain too manual. A future workflow-polish item
  now covers searchable ticker/name discovery, user-scoped watchlists,
  sortable/filterable symbol tables, bulk import, duplicate handling,
  active/inactive symbols, optional groups/tags, provider/source support
  labels, ETF/index substitution guidance, and eventual recommendation-universe
  selection from watchlists without implying execution support.
- Operator glossary and explainable metric tooltips — many current surfaces
  expose abbreviations and metrics such as `RR`, `CONF`, `Score`, `DTE`,
  Expected Range, `IV`, open interest, breakevens, gross/net P&L, commissions,
  provider readiness, paper lifecycle, and replay payoff preview. A future
  workflow-polish item now covers a shared glossary registry plus accessible
  in-context help, while keeping confidence/score separate from probability of
  profit and preserving paper-only/non-execution guardrails. `10C1` has landed
  the shared foundation and first low-risk integrations; `10C2` has landed the
  Recommendations score/risk-label rollout; `10C3` through `10C5` have landed
  Orders, Analysis, Replay, and closure-audit coverage for the current
  in-context scope. Optional glossary/reference-page rollout remains open.

## Deployment State
- URL: https://macmarket.io
- Tunnel: Cloudflare Tunnel (cloudflared Windows service, auto-start)
- Backend: uvicorn on `127.0.0.1:9510`
- Frontend: Next.js on `0.0.0.0:9500`
- DB: SQLite at `C:\Dashboard\MacMarket-Trader\macmarket_trader.db`
- Backup: daily 3 AM via `MacMarket-DB-Backup` scheduled task
- Scheduler: every 5 min via `MacMarket-StrategyScheduler` scheduled task
- Alpha users: 3 (admin + 2 approved)
- Alpaca paper API keys: configured, `BROKER_PROVIDER=mock` (execution phase
  not active)

## Test Counts (last verified 2026-04-30)
- pytest: 271 collected
- vitest: 199
- Playwright: 31

## Core product pillars
1. **Strategy Workbench** (`/analysis`) — primary setup entry, links into
   Recommendations.
2. **Recommendations Workspace** (`/recommendations`) — ranked queue,
   promote → persisted lineage, full provenance.
3. **Replay Lab** (`/replay-runs`) — deterministic historical replay with
   step-by-step approved/rejected outcomes.
4. **Paper Orders** (`/orders`) — stage from recommendation lineage, fill
   simulation, position lifecycle, close + reopen.
5. **Scheduled Strategy Reports** (`/schedules`) — recurring ranked scans
   with email delivery and run history.
6. **Symbol Analyze** (`/analyze`) — per-symbol snapshot for ad-hoc lookup.

## Operator click path (tester quickstart)
1. `/dashboard` → "Start guided paper trade" → `/analysis?guided=1`.
2. Pick symbol + strategy → "Refresh analysis" → "Create recommendation".
3. `/recommendations?guided=1&recommendation=…` → "Make active" auto-advances.
4. `/replay-runs?guided=1&…` → "Run replay now" auto-advances if stageable.
5. `/orders?guided=1&…` → "Stage paper order now" → blotter with lineage.
6. Close position → gross/net P&L with fees; reopen within 5 min if needed.

## LLM role
**Today:** extract events, summarize catalysts, explain context. Engines
decide and size; LLMs never produce trade decisions.
**Later:** richer narrative explanation of replay outcomes and recommendation
provenance. Decision logic remains deterministic.

## Multi-asset expansion policy
Equities are first-class today. Options now support a scoped paper-first
research/replay-preview/manual-close lifecycle centered on
`/recommendations`, plus durable paper-options visibility on `/orders` from
Phase 9B. Current provider/source/as-of parity is closed under Phase 9;
deeper provider-depth work remains future. Phase 10 now organizes deferred
options polish, provider-depth planning, and crypto architecture planning;
crypto implementation remains future work. Cross-mode `expected_range`
semantics
remain spec-defined only until preview payloads, scoring, replay, and later
mode-native operator surfaces carry method-tagged fields per mode.

## Detailed change log
Pass-by-pass detail (every closeout, every test count delta, every fix) is
preserved in git history. Run `git log --oneline -- docs/roadmap-status.md`
for the chronological list, or `git log -p docs/roadmap-status.md` for full
diffs. Notable recent inflection points:

- 2026-04-29 — Phase 8 master blueprint expanded: `docs/options-architecture.md`
  was tightened into a master plan and new companion docs now define the
  replay preview design, paper lifecycle design, operator risk UX design, and
  Phase 8 test matrix. This stayed docs-only; no schema, migration, replay,
  order-lifecycle, or execution behavior changed.
- 2026-04-29 — Analysis / Recommendations chart UX pass: workflow charts now
  default to compact presets instead of crowded overlays, surface hover
  snapshot values for time / close / volume plus visible indicators only, and
  show a value-rich legend with quick hide toggles. This stayed frontend-only;
  scoring, replay, orders, schemas, and provider execution behavior were not
  changed.
- 2026-04-29 — Analysis / Recommendations chart UX pass 2: workflow charts now
  render coordinated lower panels for volume and RSI with synchronized
  inspection context across panels, while keeping MACD, ATR, HACO parity,
  advanced indicator settings, and Playwright interaction coverage deferred.
  This remained frontend-only; options stayed research-only and no
  recommendation, replay, order, or provider behavior changed.
- 2026-04-29 — Phase 8A planning started: `docs/options-architecture.md`
  added with safe follow-on slices for read-only option contracts, replay,
  paper lifecycle, and operator risk UX. This was a docs-only pass; no
  schema, migration, or application-code changes landed.
- 2026-04-29 — Phase 8B complete for the current non-persisted
  research-visibility scope: Recommendations now exposes a read-only options
  research preview sourced from the protected Analysis setup contract,
  Analysis suppresses persisted recommendation creation for non-equities, and
  options-mode execution CTAs remain intentionally unavailable. This stayed
  frontend-only; no schema, migration, replay, order-lifecycle, or execution
  behavior changed.
- 2026-04-29 — Phase 8C planning pass: `docs/options-architecture.md` now
  defines options replay as a read-only, non-persisted replay-preview mode for
  defined-risk structures first, with vertical debit spreads and iron condor as
  the initial targets. Existing equity replay remains isolated, while staging,
  options paper lifecycle, and live routing stay deferred to later slices.
- 2026-04-29 — Phase 8C2 complete: isolated pure options payoff math landed in
  `src/macmarket_trader/options/payoff.py` with focused backend tests covering
  long-option primitives, vertical debit spreads, iron condor, blocked naked
  shorts, and invalid input handling. This stayed schema-free, route-free,
  persistence-free, and UI-free; existing equity replay behavior was unchanged.
- 2026-04-29 — Phase 8C3 complete: a dedicated read-only options replay
  preview contract landed at `POST /user/options/replay-preview`, backed by the
  isolated payoff helper and focused backend tests for ready/blocked/
  unsupported responses plus non-persistence. This remained schema-free,
  non-persisted, UI-free, and separate from existing equity replay routes.
- 2026-04-29 — Phase 8C4 complete: Recommendations options research mode now
  exposes an operator-facing replay payoff preview panel that calls the
  read-only preview contract, renders compact expiration payoff summaries and
  blocked reasons safely, and keeps persisted replay/order/staging CTAs
  suppressed. This remained frontend-focused and non-persisted.
- 2026-04-29 — Phase 8C5 closure review complete for the current read-only,
  non-persisted replay-preview scope: roadmap/design docs now align on the
  shipped 8C boundary, Expected Move / Expected Range remains explicitly
  contextual research input rather than payoff math, and the operator copy now
  says that expected range does not change expiration payoff math or enable
  execution.
- 2026-04-29 — Phase 8D1 design checkpoint complete: the options paper
  lifecycle plan now compares extending current equity tables versus a
  separate options-specific persistence branch, recommends dedicated
  structure/leg persistence, defines draft open/close payload shapes, and
  keeps schema, migration, commission application, and operator UI work
  deferred to later 8D slices.
- 2026-04-29 — Phase 8D4 complete: a dedicated open-only paper options
  lifecycle path now exists at `POST /user/options/paper-structures/open`,
  backed by the options repository contracts and validation helpers. Supported
  defined-risk structures create options-specific order and position headers
  plus legs without touching equity orders, replay runs, staged orders, or
  live routing. Close behavior, commission application, and frontend operator
  UI remain deferred to later 8D slices.
- 2026-04-29 — Phase 8D5 complete for the current manual-close scope: open
  paper option positions can now close through
  `POST /user/options/paper-structures/{position_id}/close`, which validates
  full-leg manual close input, blocks double close and cross-user access,
  persists options-specific trade headers plus legs, and computes gross P&L
  without applying commissions yet. Expiration settlement, commission
  application, and frontend operator UI remain deferred.
- 2026-04-29 — Phase 8D6 complete for the current manual-close scope:
  `commission_per_contract` now applies per contract per leg on both the open
  and manual-close events for the dedicated options paper lifecycle branch.
  Open responses now expose paper opening commissions, manual-close trade rows
  now persist `total_commissions` and `net_pnl`, trade legs now persist
  commission and net values, and existing equity `commission_per_trade`
  behavior remains untouched. Expiration settlement and frontend operator UI
  remain deferred.
- 2026-04-29 — Phase 8D7 complete for the current paper-only manual-close
  scope: Recommendations options research preview now includes a separate
  paper option lifecycle panel with persisted paper open/manual-close actions,
  explicit `commission_per_contract` guardrails and example math, same-origin
  open/close proxies, and in-memory close inputs/results for the newly opened
  position only. Replay payoff preview remains read-only/non-persisted, equity
  workflows remain untouched, and broader Orders parity plus expiration
  settlement remain deferred.
- 2026-04-29 — Phase 8D8 closure/audit complete for the current paper-only
  manual-close scope: roadmap/design/test docs now align on `8D1` through
  `8D8`, the Recommendations options surfaces now keep replay preview wording
  distinct from the persisted paper lifecycle wording, proxy tests now cover
  success plus failure pass-through behavior, and the manual smoke checklist
  is documented. Expiration settlement, broader Orders parity, and `8E` risk
  UX remain deferred.
- 2026-04-29 — Phase 8E1 complete for the current Recommendations options
  research surface: a compact `Structure risk` layer now summarizes structure
  type, debit/credit, max profit/loss, breakevens, expiration / DTE, Expected
  Range status/context, replay-preview status, paper lifecycle state, and
  manual-close gross/commission/net outcome while keeping research preview,
  replay payoff preview, and persisted paper lifecycle visually distinct.
- 2026-04-29 — Phase 8E2 complete for the current Recommendations options
  provider/source/as-of and data-quality warning scope: the same `Structure
  risk` layer now surfaces workflow source, chain source/as-of, Expected
  Range provenance/as-of, safe `Source unavailable` / `As-of unavailable`
  rendering, and provider-plan/payload warnings for missing chain, IV,
  Greeks, open interest, missing expiration/DTE, and SPX/NDX index-data
  caveats without changing backend behavior or widening the page into a new
  dashboard.
- 2026-04-29 — Phase 8E3 complete for the current guided Recommendations
  options workflow UX: the same surface now adds a five-step operator guide,
  clearer paper-save wording, more explicit manual-close exit-premium help,
  a stronger post-close result state, and lighter progressive disclosure for
  detailed caveats without changing backend behavior or widening the feature
  scope.
- 2026-04-29 — Phase 8E closure review complete for the current
  Recommendations options surface: replay preview, read-only research context,
  and persisted paper-only lifecycle wording are now aligned; the replay
  preview no longer echoes execution-enabled copy; the current operator risk,
  provider/source, Expected Range, guided workflow, and manual-close clarity
  gates are documented as satisfied without implying full Phase 8 closure.
- 2026-04-29 — Phase 8F final closure complete for the current scoped
  paper-first options capability: frontend (`npm test`, `npx tsc --noEmit`)
  plus backend (`tests/test_options_paper_open_lifecycle.py`,
  `tests/test_options_paper_close_lifecycle.py`,
  `tests/test_options_replay_preview.py`) validation passed; docs now mark
  `8A` through `8F` complete for the scoped paper-first capability while
  keeping expiration settlement, assignment/exercise automation, persisted
  options recommendations, broader Orders parity, advanced Expected Move
  visualization, and live routing/execution explicitly deferred.
- 2026-04-29 — Phase 9 planning update complete: roadmap now defines `9A`
  through `9D` as the next options maturity phase focused on durable operator
  visibility and provider/data-quality parity, renumbers later Alpaca/crypto
  phases to preserve ordering, and keeps settlement, assignment, persisted
  options recommendations, live routing, and broker integration explicitly
  deferred.
- 2026-04-29 — Phase 9B complete for the current durable paper-options
  Orders/Positions visibility scope: a user-scoped paper-options list
  contract now surfaces saved open and closed paper option lifecycle records
  through Orders, using the dedicated options persistence path without
  changing equity order/replay behavior, live-routing boundaries, or options
  lifecycle math. Frontend and targeted backend validation passed.
- 2026-04-29 - Phase 9C1 complete for the current provider/source/as-of parity
  micro-pass: Analysis options Expected Range and chain preview copy now uses
  existing source/as-of/provenance fields and safe fallback text, Orders
  durable paper-options rows document that full provider/source metadata remains
  research-preview context, and Provider Health carries options/index data
  caveats as readiness context only. Remaining 9C parity and 9D visualization
  stay planned.
- 2026-04-29 - Phase 9C complete for the current provider/source/as-of parity
  closure scope after audit: Analysis, Recommendations, Orders durable
  paper-options rows, Provider Health, and operator guidance now present source,
  as-of/provenance, provider-plan limitations, and durable metadata limitations
  consistently where existing payload fields allow. No backend, schema,
  lifecycle, commission, equity, provider-fetch, or execution behavior changed.
  Full Phase 9D implementation remained planned.
- 2026-04-29 - Phase 9D1 design checkpoint complete for advanced Expected
  Move / Expected Range visualization: docs now recommend a compact reusable
  horizontal range bar using existing expected-range, breakeven, expiration/DTE,
  max-profit/max-loss, and already-loaded replay payoff fields only. The
  implementation remains deferred, and probability of profit, broker
  mark-to-market, settlement, assignment/exercise, provider probes, scoring
  changes, live routing, and math changes stay out of scope.
- 2026-04-30 - Phase 9D2 complete for the first reusable Expected Range
  visualization slice: a frontend-only component now renders a compact
  horizontal range bar inside Recommendations `Structure risk` using existing
  expected-range, breakeven, expiration/DTE, risk, source/as-of, and provenance
  fields only. Focused frontend tests cover computed, blocked, missing, safe
  rendering, and safety-copy states. No backend, schema, provider-fetch,
  lifecycle, commission, equity, recommendation-generation, payoff-math, or
  execution behavior changed.
- 2026-04-30 - Phase 9D closure complete for the current Recommendations
  Expected Range visualization scope: audit/polish confirmed lower/upper
  bounds, breakeven markers, blocked/missing states, safe invalid-number
  rendering, compact placement, and research-only safety copy. A tiny label
  polish now distinguishes a derived range midpoint from an actual
  current/reference price. Frontend validation passed at 160 vitest tests plus
  clean TypeScript; no backend, schema, provider, lifecycle, commission,
  equity, payoff, recommendation-generation, routing, settlement, assignment,
  exercise, naked-short, or probability behavior changed.
- 2026-04-30 - Phase 9 status/closure audit complete: current Phase 9 scope is
  closed across durable options Orders visibility, provider/source/as-of parity
  on the practical options surfaces, and the Recommendations Expected Range
  visualization. Remaining items are explicitly deferred future/provider-depth
  work rather than blockers for Phase 9 closure.
- 2026-04-30 - Phase 10 planning move complete: roadmap now treats Phase 10 as
  a documentation-first sequencing and safe-polish track for deferred options,
  provider-depth, replay/history, settlement-design, and crypto-architecture
  work. The initially recommended first implementation slice was `10A1`, an optional
  Analysis Expected Range visualization using existing payload fields and the
  existing reusable component only. Live routing, real brokerage execution,
  expiration settlement implementation, assignment/exercise automation, naked
  shorts, persisted options recommendations, options replay persistence,
  probability/margin modeling, and crypto implementation remain explicitly
  later/not-now.
- 2026-04-30 - Phase 10A1 complete: Analysis options setup now reuses the
  existing Expected Range visualization component with current setup payload
  fields only. The slice stayed frontend-only and keeps Expected Range as
  research context that does not change payoff math or approve execution.
  Backend behavior, schema, provider probes, lifecycle math, commission math,
  equity behavior, recommendation generation, live routing, settlement,
  assignment/exercise, naked-short support, probability modeling, and crypto
  implementation remain unchanged.
- 2026-04-30 - Phase 10B1 complete: Orders durable paper-options visibility
  now has a frontend-only display/readability polish pass. The section clearly
  describes display-only durable paper lifecycle records, no broker orders
  sent, manual close remaining in Recommendations, provider/source/as-of
  metadata limits, open versus manually closed paper states, compact
  debit/credit/risk/commission/gross/net summaries, and expandable leg detail
  tables using existing persisted options lifecycle fields only. No backend,
  schema, provider, lifecycle, commission, equity, replay, recommendation,
  routing, settlement, assignment/exercise, naked-short, probability, or crypto
  behavior changed.
- 2026-04-30 - Future symbol discovery and watchlist management roadmap item
  added: a docs-only planning note now tracks searchable ticker/name discovery,
  user-scoped searchable/sortable watchlists, bulk import, duplicate handling,
  active/inactive symbols, optional tags/groups, provider/source support
  labels, SPX/NDX versus SPY/QQQ substitution guidance, and eventual
  recommendation-universe selection from watchlists. This remains
  recommendation-universe management only, with no application code, schema,
  provider probes, live routing, brokerage execution, or recommendation
  generation behavior changed.
- 2026-04-30 - Symbol discovery and watchlist management design checkpoint
  complete (`10W1`): `docs/symbol-watchlist-design.md` now records the
  current-state inventory, symbol-discovery UX, watchlist-management UX,
  recommendation-universe selection model, data-model alternatives, hybrid
  recommendation, provider assumptions, future tests, and implementation
  slices. Existing Phase 10 numbering is preserved, with `10D` still reserved
  for expiration-settlement design. No application code, backend behavior,
  frontend behavior, schema, provider probes, live routing, or recommendation
  generation changed.
- 2026-04-30 - Phase 10W2 complete for current comma-entry symbol workflow
  cleanup: Recommendations, Schedules, and current watchlist editing now share
  frontend-only manual symbol parsing and a parsed uppercase preview for
  comma/space/new-line input, duplicate feedback, ETF/index substitution copy,
  and concise future-watchlist guidance. Analysis now has a single-symbol
  provider-access hint. No backend behavior, schema, provider search/probes,
  watchlist storage replacement, schedule execution behavior, recommendation
  generation, equity behavior, options lifecycle behavior, live routing, or
  brokerage execution changed.
- 2026-04-30 - Phase 10W3 complete as a docs-only schema/read-model design
  checkpoint: the symbol/watchlist design now recommends a compatibility-first
  `user_symbol_universe` plus `watchlist_symbols` model, preserving current
  `watchlists.symbols` and schedule payload symbol snapshots while planning
  normalized duplicate handling, active/inactive state, tags/notes, nullable
  provider metadata, resolver behavior, migration/backfill, rollback, and
  future tests. No application code, backend behavior, frontend behavior,
  schema, migration, provider search/probes, recommendation generation,
  schedule execution behavior, live routing, or brokerage execution changed.
- 2026-04-30 - Phase 10W4 complete for the additive symbol-universe
  schema/migration foundation: `user_symbol_universe` and
  `watchlist_symbols` now exist as ORM models and Alembic tables with nullable
  provider metadata, `active` defaults, uniqueness constraints, indexes, and
  focused schema/migration tests. Existing `watchlists.symbols` JSON/list
  behavior, strategy schedule payload symbols, recommendation generation,
  schedule execution, frontend UI, provider search/probes, live routing, and
  brokerage execution remain unchanged.
- 2026-04-30 - Phase 10W5 complete for the backend-only repository/read-model
  and resolver foundation: `SymbolUniverseRepository` now supports internal
  upsert/get/list/active-state helpers for user-symbol rows plus normalized
  watchlist membership add/list/deactivate/remove helpers, including
  snapshot-only membership without provider metadata. `SymbolUniverseResolver`
  normalizes, dedupes, applies exclusions, and combines pinned, manual,
  watchlist, and active universe symbols in deterministic order. Existing
  watchlist JSON behavior, strategy schedule payload symbols, recommendation
  generation, schedule execution, frontend UI, provider search/probes, live
  routing, and brokerage execution remain unchanged.
- 2026-04-30 - Phase 10W6 complete for frontend-only current watchlist table
  UI polish: Schedules now shows searchable/sortable saved watchlists with
  symbol counts, normalized symbol chips, per-list symbol filtering, duplicate
  feedback, ETF/index substitution guidance, concise future normalized-list
  copy, and per-symbol removal using the existing watchlist update route.
  Existing `watchlists.symbols` JSON behavior, strategy schedule payload
  symbols, recommendation generation, schedule execution, normalized
  symbol-universe table usage, provider search/probes, live routing, and
  brokerage execution remain unchanged.
- 2026-04-30 - Phase 10W7 complete for frontend-only bulk symbol handling and
  duplicate polish: manual symbol copy now covers commas, spaces, tabs, and new
  lines; parsed previews show safe blank-separator handling; editing a
  watchlist now offers replace or add-to-existing modes; merge mode preserves
  existing symbols first, appends newly pasted unique symbols, and reports
  duplicates ignored before submitting the same deduped `symbols` array through
  the existing watchlist update route. Existing `watchlists.symbols` JSON
  behavior, strategy schedule payload symbols, recommendation generation,
  schedule execution, normalized symbol-universe production UI, provider
  search/probes, live routing, and brokerage execution remain unchanged.
- 2026-04-30 - Phase 10W8 complete as a docs-only recommendation/schedule
  universe-selection design checkpoint: `docs/symbol-watchlist-design.md` now
  records current raw symbol-array flows, future selector modes, static schedule
  snapshot semantics, optional dynamic-watchlist risk, resolver rules, future
  preview API implications, UX concepts, tests, and implementation slices
  (`10W8A` through `10W8D`). No application code, backend behavior, frontend
  behavior, schema, provider search/probes, recommendation generation, schedule
  execution, live routing, or brokerage execution changed.
- 2026-04-30 - Phase 10W8A complete for the read-only resolved-universe
  preview helper/API: `POST /user/symbol-universe/preview` now resolves
  manual, watchlist, watchlist-plus-manual, all-active, and mixed preview
  inputs into deterministic symbol arrays with duplicate, exclusion, pinned,
  source-label, warning, and provenance metadata. The route is protected and
  user-scoped, reads only existing symbol/watchlist data, does not call
  providers, does not submit Recommendations, does not mutate schedules or
  watchlists, and does not change schema, recommendation generation, schedule
  execution, scoring, lifecycle, commission, provider-search, live routing, or
  brokerage behavior.
- 2026-04-30 - Phase 10W8B complete for the Recommendations universe selector
  UI: the Recommendations page can now preview manual, saved-watchlist,
  watchlist-plus-manual, and all-active symbol universes through the read-only
  preview API, render resolved symbols/counts/warnings/provider-metadata notes,
  and copy resolved symbols into the existing manual input only when the
  operator clicks `Use resolved symbols`. This frontend pass adds only a
  same-origin proxy plus UI/tests/docs and does not change recommendation
  generation, queue submit behavior, schedule execution, provider search,
  schema, scoring, lifecycle, commission, live routing, or brokerage behavior.
- 2026-04-30 - Phase 10W8C complete for the Schedule universe static-snapshot
  selector UI: the Schedules create/update card can now preview manual,
  saved-watchlist, watchlist-plus-manual, and all-active symbol universes
  through the read-only preview API, render resolved symbols/counts/warnings
  and provider-metadata notes, and copy resolved symbols into the existing
  schedule symbol input only when the operator clicks `Use resolved symbols in
  this schedule`. Existing Create/Update actions remain the only save path,
  schedule payloads still store the same parsed `symbols` array, scheduled
  runs still use static snapshots, and dynamic watchlist refresh, provider
  search, schema, recommendation generation, scoring, lifecycle, commission,
  live routing, and brokerage behavior remain unchanged.
- 2026-04-30 - Phase 10W8D complete for recommendation/schedule
  universe-selection closure: audit confirms the backend preview API remains
  read-only, user-scoped, provider-free, no-mutation, and preview-only;
  Recommendations and Schedules remain preview/apply only; existing queue
  submit, schedule save, and static `payload.symbols` schedule-run semantics
  remain unchanged; manual symbol parsing/guidance remains compatible. A tiny
  backend assertion now covers the preview API's no-schedule-mutation and
  no-watchlist-mutation flags. Provider-backed discovery, normalized
  symbol-universe production UI, tags/groups, dynamic watchlist refresh,
  recommendation generation changes, schedule execution changes, live routing,
  and brokerage behavior remain deferred.
- 2026-04-30 - Future operator glossary and explainable metric tooltips
  roadmap item added: a docs-only planning note now tracks concise
  hover/click/tap metric help, formulas and examples where useful, a shared
  glossary registry, optional future glossary/reference page, accessibility
  expectations, and initial terms including `RR`, `CONF`, `Score`, Expected
  Range, `DTE`, `IV`, open interest, breakevens, max profit/loss, gross/net
  P&L, equity and options commissions, provider readiness, paper lifecycle,
  and replay payoff preview. This does not change application code, schema,
  provider probes, live routing, brokerage execution, recommendation
  generation, probability modeling, payoff math, lifecycle math, or commission
  math.
- 2026-04-30 - Phase 10C1 complete for the explainable metric UX foundation:
  frontend now has a central glossary registry, reusable `MetricHelp` /
  `MetricLabel` component, focused tests for required terms and safety copy,
  and narrow first integrations in Settings commission labels, Expected Range
  visualization labels, and Provider Health readiness context. Broader
  Analysis/Recommendations/Replay/Orders rollout remains future work, and no
  backend, schema, provider, lifecycle, commission, equity, recommendation,
  routing, settlement, assignment/exercise, naked-short, probability, symbol
  discovery, watchlist, or crypto behavior changed.
- 2026-04-30 - Phase 10C2 complete for Recommendations explainable metric
  labels: compact `MetricLabel` help now appears on queue `Score`, `RR`, and
  `CONF` labels plus the options risk/paper-lifecycle labels for Expected
  Range, max profit/loss, breakevens, gross/net P&L, and options
  commissions. Frontend tests cover the rollout and safety wording. No
  backend, schema, provider, recommendation scoring, equity, lifecycle,
  payoff, commission, routing, settlement, assignment/exercise,
  symbol-discovery, watchlist, probability, or crypto behavior changed.
- 2026-04-30 - Phase 10C3 complete for Orders explainable metric labels:
  compact `MetricLabel` help now appears on equity Orders P&L/fee labels and
  durable paper-options P&L, commission, max profit/loss, breakeven, paper
  lifecycle, and leg result labels. Frontend tests cover the Orders source
  wiring and durable options rendering. No backend, schema, provider,
  recommendation scoring, equity behavior, lifecycle math, payoff math,
  commission math, routing, Orders actions, settlement, assignment/exercise,
  symbol-discovery, watchlist, probability, or crypto behavior changed.
- 2026-04-30 - Phase 10C5 closure audit complete for explainable metric
  glossary/tooltips current scope: Settings, Provider Health, Expected Range,
  Recommendations, Orders, Analysis, and Replay now have compact in-context
  help on the highest-confusion labels. Tiny glossary safety-copy polish and
  focused tests keep confidence/score separate from probability of profit,
  Provider readiness separate from live routing/broker execution, and Replay
  payoff preview separate from broker mark-to-market simulation. Optional
  glossary/reference-page work remains future, and Phase 10 remains open.
- 2026-04-29 — Phase 7A/7B complete for current equity/paper scope:
  commission-aware gross/net realized paper P&L, per-user commission
  settings, replay/order/open-position fee previews, orders/settings UI
  updates, and equity close-math fee application. `commission_per_contract`
  storage landed, but options parity remains open.
- 2026-04-29 — Phase 7C complete for current paper/provider-readiness scope:
  Admin / Provider Health expanded into an operator-readiness console with
  explicit Alpaca paper readiness plus FRED and news readiness entries. This
  remains a paper/provider trust gate only; no live brokerage execution was
  enabled.
- 2026-04-29 — Pass 4: `display_id`, per-user risk dollars, Settings page,
  invite-email welcome CTA, schedules timezone display, MFA runbook, brand
  header on pre-auth, dashboard 401 hardening (`pending-approval` redirect).
- 2026-04-28 — Phase 6 close-out: cancel staged order, reopen closed position
  (5-min undo), email logo base64 inlining, scheduler runner script,
  in-browser welcome guide, sticky Active Trade banner, readable lineage
  breadcrumb, conditional CTA pulse states, replay step bar labels.
- 2026-04-16 — Polygon hardening: `SymbolNotFoundError`, `DataNotEntitledError`,
  options chain preview, index symbol normalization. Admin user-management
  hardening pass 1 + 2 (suspend, unsuspend, force re-login, hard delete,
  invite revoke/resend, role toggle).
- 2026-04-15 — Phase 6 close-trade lifecycle backend; Polygon live market
  data; transactional email polish; operational readiness audit; second-
  operator readiness checklist in runbook.
- 2026-04-12 — Phase 3 (paid beta scaffolding) + Phase 4 (vendor integration)
  closeouts.
- 2026-04-04 — Phase 1 closeout passes (provider truth, identity
  reconciliation, market-mode foundation, Windows deployment validation).
- 2026-04-03 — Initial Phase 1 hardening passes.
