# MacMarket-Trader Product Roadmap Status (Private Alpha)

Last updated: 2026-04-03

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
MacMarket-Trader remains in **Phase 1 — Private alpha hardening** for operator trust and workflow coherence.

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

## Phase 1 open items

- Add broader end-to-end UI tests for full in-session loop validation (Analysis -> Recommendations -> Replay -> Orders).
- Expand integration tests around auth-initialization edge timing under real Clerk session turnover.
- Tighten consistency checks so dashboard/replay/orders/recommendations source badges can be regression-tested together.
- Continue replacing remaining ad-hoc inline styles on core pages with reusable operator-console components.
- Complete final private-alpha operator runbook pass with screenshots/examples.

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
- which symbols matter today
- which strategy is active
- which setups are worth trading
- what levels matter
- what to ignore
