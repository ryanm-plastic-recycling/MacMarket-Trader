# Roadmap Status (Private Alpha)

Last updated: 2026-04-03

MacMarket-Trader remains in **Phase 1 — Private alpha hardening** for operator trust and workflow coherence.

## Phase 1 complete items

- Strategy Workbench (`/analysis`) is the primary setup entry and links into Recommendations.
- Core workflow surfaces exist and are connected: Recommendations -> Replay -> Orders.
- Workflow source labeling is explicit on core pages and fallback mode is visibly tagged.
- Same-origin workflow API access defaults to server-side session auth resolution with bearer fallback only.
- Inline action feedback is implemented (loading/success/error with retry) across core operator workflow pages.
- Admin users page and Account page present operator-facing identity/authorization fields (role, approval, MFA, last seen/authenticated, invite state when available).
- Provider health page includes operational impact language for fallback-vs-provider interpretation.

## Phase 1 open items

- Add broader end-to-end UI tests for full in-session loop validation (Analysis -> Recommendations -> Replay -> Orders).
- Expand integration tests around auth-initialization edge timing under real Clerk session turnover.
- Tighten consistency checks so dashboard/replay/orders/recommendations source badges can be regression-tested together.
- Continue replacing remaining ad-hoc inline styles on core pages with reusable operator-console components.
- Complete final private-alpha operator runbook pass with screenshots/examples.

## Phase 2 started early (kept bounded)

These foundations stay in place but are not the focus until Phase 1 closes:

- Symbol Analyze workspace.
- Scheduled strategy reports (schedule CRUD + run-now + CLI due runner).
- Operator indicator registry/framework and persisted indicator preferences.

## Operator click path (tester quickstart)

1. Open `/analysis` and choose symbol/timeframe/strategy.
2. Click **Create recommendation from this setup**.
3. In `/recommendations`, review strategy/timeframe/levels/source and open replay.
4. In `/replay-runs`, run replay and verify approved/rejected step outcomes and source.
5. In `/orders`, stage paper order and confirm recommendation linkage + workflow source.
6. Use `/admin/provider-health` to confirm whether workflow ran on provider or explicit fallback.
