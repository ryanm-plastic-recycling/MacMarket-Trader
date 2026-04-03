# AGENTS.md

## 1. Canonical documents

- Read `README.md` first. Treat it as the canonical architecture charter.
- Do not shrink the root README into a short status page.
- Keep docs aligned with implementation.
- Preserve the HACO / HACOLT policy from the README.

## 2. Product thesis

- MacMarket-Trader is a research-first, event-driven trading system.
- LLMs extract, summarize, classify, and explain; deterministic logic decides, sizes, and routes.
- Security, approval gating, auditability, deterministic risk, and workflow traceability are mandatory.
- This is an operator console first, not a consumer finance app.

## 3. Product center and workflow

### Primary workflow
- **Strategy Workbench / Analysis** is the primary entry point for creating and reviewing setups.
- **Recommendations** is the flagship review and execution-prep surface.
- **Replay** validates the recommendation path before paper execution.
- **Orders** is the paper blotter for staged and simulated execution outcomes.

### Supporting workflow
- **Dashboard** is the operator hub.
- **HACO / HACOLT** are important supporting technical context and research tools, but not the product center.
- **Admin / Invites / Users / Account / Provider Health** must feel like real operator tools, not placeholders.

### Workflow coherence rules
- If provider-backed market data is configured, user-facing recommendation / replay / order flows must prefer provider-backed bars over demo bars.
- Fallback mode must be explicit, never hidden.
- If a workflow is running on fallback data, label it clearly and consistently across all related pages.
- Recommendations must always show strategy, timeframe, and workflow source.
- Replay and Orders must explain their relationship to the originating recommendation or setup.

## 4. Source-of-truth rules

### Authorization and identity
- The local app database is the source of truth for:
  - `approval_status`
  - `app_role`
- Never overwrite local `approval_status` or `app_role` from external auth claims.
- External auth is for identity/session verification, not authorization truth.

### Market data and workflows
- Never silently mix provider-backed chart context with fallback-generated recommendation / replay / order workflows.
- Any workflow page must state whether it is using provider data or fallback data.
- If provider health is degraded or fallback, workflow pages must say so explicitly.

### Recommendations and chart context
- A selected recommendation must render chart context from the same workflow source used to generate it.
- Do not display levels, signals, or targets against a chart sourced from a different bar set.
- Never use numeric bar indices as user-facing chart time axes when canonical timestamps are available.

## 5. Auth and identity rules

- Keep Clerk sign-in / sign-up routes compatible with Clerk requirements.
- Keep middleware public-route configuration Clerk-compatible.
- Prefer server-side session auth for same-origin Next API routes when possible.
- Do not allow brittle client-supplied bearer-token flow to dominate same-origin auth paths.
- Do not leave stale `401` / `Invalid token` banners visible after a later successful fetch.
- Normalize identity data into operator-friendly text.
- Do not render raw Clerk template placeholders like `{{user.primary_email_address.email_address}}` in Account or Admin surfaces.
- Existing approved/admin users must remain approved/admin after login or sync.

## 6. Charting and indicator rules

### Canonical chart rules
- Any chart layer derived from the same bar series must share one canonical indexed time base.
- Price bars, signal markers, strategy levels, HACO strip, and HACOLT strip must remain aligned under zoom/pan.
- Do not ship unsynced visual indicator strips as the primary implementation.
- Do not ship charts showing garbage time axes like `1970` when real timestamps are available.

### Indicator system
- Charts must support **operator-selectable indicators**.
- Indicator visibility must be explicit and user-controlled, not hardcoded page by page.
- Persist indicator selections per user or in stable local preferences when user-level persistence is not yet available.
- Indicator controls should be available on:
  - Strategy Workbench / Analysis
  - Recommendations chart context
  - HACO Context page

### Supported indicator categories
- **Trend overlays**
  - SMA
  - EMA
  - VWAP
  - Anchored VWAP
- **Volatility**
  - ATR
  - Bollinger Bands
  - Keltner Channels
- **Structure / levels**
  - Prior day high / low
  - Opening range
  - Gap levels
  - Key support / resistance
- **Momentum / confirmation**
  - RSI
  - MACD
- **Volume**
  - Volume bars
  - Relative volume
- **HACO context**
  - HACO
  - HACOLT

### Indicator UX rules
- Keep default charts clean and professional; do not overload the page by default.
- Strategy overlays and indicator overlays must be visually distinct.
- A chart should clearly display:
  - symbol
  - timeframe
  - source
  - strategy
  - enabled indicators

## 7. UI and operator-console rules

- Every core operator page must implement all four states:
  - loading
  - empty
  - error
  - populated
- Every primary page must answer:
  - what is this for?
  - what should the operator do next?
  - what data supports that action?
- Avoid placeholder-only pages.
- Favor reusable console components and a consistent operator-console design language.
- Do not expose raw backend/provider errors directly as the primary UX.
- Convert provider/backend failures into operator-actionable guidance.
- Use lightweight inline progress, success, and error feedback for actions.
- Avoid modal interruption for routine operator tasks.
- Do not let one nested client-side fetch failure blank an otherwise usable operator page.
- Keep the UI dark, professional, data-first, and desk-like by default.
- Theme toggle is allowed, but must be SSR-safe and persist correctly.
- Core console pages should not rely primarily on ad hoc inline styles.

## 8. Strategy Workbench / Analysis rules

- Treat Strategy Workbench / Analysis as the primary entry point for operator workflow.
- A setup should be born in Analysis, reviewed in Recommendations, validated in Replay, and staged in Orders.
- Strategy Workbench should support:
  - symbol selection
  - timeframe selection
  - strategy selection
  - chart rendering
  - strategy overlays / levels
  - source labeling
  - notes explaining why the strategy is active or inactive
- Recommended initial strategy set:
  - Event Continuation
  - Breakout / Prior-Day High
  - Pullback / Trend Continuation
  - Gap Follow-Through
  - Mean Reversion
  - HACO Context
- HACO is supporting technical context, not the flagship workflow.

## 9. Admin, account, and onboarding rules

### Admin
- Admin surfaces must show current users, not only pending users or invites.
- Persist and display practical account metadata such as:
  - last seen
  - last authenticated
  - role
  - approval
  - MFA state
  - invite state when available

### Account
- Account page must show useful operator-facing identity and authorization state.
- Account should include:
  - real email
  - display name
  - role
  - approval status
  - MFA state
  - sign-out affordance
  - theme preference when available

### Onboarding
- Invite-only onboarding is the primary private-alpha path unless explicitly changed.
- Do not treat public self-signup as the main go-to-market flow.
- The app should be presentable in local/dev mode with deterministic seed data for core workflows.

## 10. Development and testing rules

- Prefer small, bounded changes.
- Run tests before finishing.
- For backend changes, run `pytest`.
- For frontend changes, ensure:
  - `npm install`
  - `npm test`
  - `npm run build`
  succeed.
- Keep dependency changes intentional.
- Keep lockfiles committed when changed.
- Keep docs aligned with implementation.
- Keep Windows dev path and live runtime path separate.
- Keep `scripts/create_shareable_backup.bat` as the canonical backup/export script if present.

## 11. Guardrails

- Do not replace real auth with mock auth in production-facing paths.
- Do not point browser code to localhost for hosted deployments.
- Do not delete canonical architecture sections from the root README.
- Do not add cosmetic UI work ahead of operator workflow value.
- Do not downgrade data-driven operator pages back into placeholders.
- Preserve HACO in two places:
  - dedicated workspace
  - dashboard-integrated supporting module
- Do not silently mix workflow sources.
- Do not ship charts with broken time axes or desynced strips.
- Do not leave stale error banners visible after a successful refresh.
- Do not let Recommendations, Replay, and Orders drift into disconnected mini-apps.

- ## Roadmap discipline
- Always refer work back to the product roadmap phases.
- Unless explicitly told otherwise, assume the repo remains in **Phase 1 — Private alpha hardening** until the remaining Phase 1 gate items are truly complete.
- Do not allow Phase 2 feature sprawl to undermine Phase 1 trust and workflow coherence.
- When adding or modifying major features, update a roadmap status doc showing what is complete vs open for the current phase.
- Preserve the product center:
  - Strategy Workbench / Analysis
  - Recommendations
  - Replay
  - Paper Orders
- Treat Symbol Analyze, Scheduled Strategy Reports, and richer AI orchestration as Phase 2+ foundations unless they materially help Phase 1 workflow trust.
