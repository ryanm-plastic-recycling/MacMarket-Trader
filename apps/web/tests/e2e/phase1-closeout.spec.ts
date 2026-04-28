import { expect, test } from "@playwright/test";

function chartPayload() {
  const candles = Array.from({ length: 40 }, (_, idx) => ({
    time: `2026-01-${String((idx % 28) + 1).padStart(2, "0")}`,
    open: 100 + idx,
    high: 101 + idx,
    low: 99 + idx,
    close: 100.5 + idx,
    volume: 1_000_000 + idx * 1_000,
  }));
  return { symbol: "AAPL", timeframe: "1D", data_source: "polygon", fallback_mode: false, candles, heikin_ashi_candles: candles };
}

// Intercept all /api/** requests so no call proxies to the Python backend (not running in e2e).
// The broad catch-all is registered first (lowest priority); test-level mocks registered
// later in each test body override it for their specific endpoints.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not mocked in e2e" } });
  });
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({ json: { app_role: null, approval_status: "approved" } });
  });
});

test("analysis -> recommendations -> replay -> orders click path with lineage ids + zero-fill messaging", async ({ page }) => {
  await page.route("**/api/user/strategy-registry", async (route) => {
    await route.fulfill({ json: [{ strategy_id: "event_continuation", display_name: "Event Continuation", market_modes: ["equities"] }] });
  });
  await page.route("**/api/user/analysis/setup**", async (route) => {
    await route.fulfill({
      json: {
        market_mode: "equities",
        workflow_source: "provider",
        strategy: "Event Continuation",
        active: true,
        active_reason: "phase1 e2e",
        trigger: "above prior-day high",
        entry_zone: { low: 120, high: 122 },
        invalidation: { price: 118, reason: "breakdown" },
        targets: [126, 129],
        confidence: 0.66,
        filters: ["trend"],
      },
    });
  });
  await page.route("**/api/charts/haco**", async (route) => route.fulfill({ json: chartPayload() }));
  // Single handler for all recommendations endpoints — dispatch by URL.
  await page.route("**/api/user/recommendations**", async (route) => {
    const url = route.request().url();
    if (url.includes("/generate")) {
      await route.fulfill({ json: { recommendation_id: "rec-phase1-e2e", market_data_source: "polygon", fallback_mode: false } });
      return;
    }
    if (url.includes("/queue")) {
      await route.fulfill({ json: { queue: [], summary: { total: 0, top_candidate_count: 0, watchlist_count: 0, no_trade_count: 0 } } });
      return;
    }
    await route.fulfill({
      json: {
        items: [{
          id: 1,
          created_at: "2026-04-04T00:00:00Z",
          symbol: "AAPL",
          recommendation_id: "rec-phase1-e2e",
          market_data_source: "polygon",
          fallback_mode: false,
          payload: {
            thesis: "Deterministic setup",
            catalyst: { type: "earnings" },
            entry: { setup_type: "Event Continuation", zone_low: 120, zone_high: 122, trigger_text: "breakout hold" },
            invalidation: { price: 118, reason: "failed hold" },
            targets: { target_1: 126, target_2: 129 },
            quality: { expected_rr: 1.8, confidence: 0.67 },
            workflow: { timeframe: "1D", market_data_source: "polygon", fallback_mode: false },
          },
        }],
      },
    });
  });
  await page.route("**/api/user/replay-runs", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { id: 22, recommendation_id: "rec-phase1-e2e", market_data_source: "polygon", fallback_mode: false, summary_metrics: { recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0 } } });
      return;
    }
    // has_stageable_candidate: true enables "Go to Paper Order step" after run completes
    await route.fulfill({ json: { items: [{ id: 22, symbol: "AAPL", source_recommendation_id: "rec-phase1-e2e", created_at: "2026-04-04", recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0, market_data_source: "polygon", fallback_mode: false, has_stageable_candidate: true }] } });
  });
  await page.route("**/api/user/replay-runs/22", async (route) => {
    await route.fulfill({ json: { id: 22, symbol: "AAPL", source_recommendation_id: "rec-phase1-e2e", source_strategy: "Event Continuation", market_data_source: "polygon", fallback_mode: false, summary_metrics: { recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0 }, thesis: "Deterministic setup", key_levels: { entry: { zone_low: 120, zone_high: 122 }, invalidation: { price: 118 }, targets: { target_1: 126, target_2: 129 } } } });
  });
  await page.route("**/api/user/replay-runs/22/steps", async (route) => {
    await route.fulfill({ json: { items: [{ id: 1, step_index: 1, recommendation_id: "rec-phase1-e2e", approved: false, rejection_reason: "risk gate", pre_step_snapshot: { current_heat: 0, open_positions_notional: 0, equity: 10000 }, post_step_snapshot: { current_heat: 0, open_positions_notional: 0, equity: 10000 } }] } });
  });
  await page.route("**/api/user/orders**", async (route) => {
    const url = route.request().url();
    if (url.includes("/portfolio-summary")) {
      await route.fulfill({ status: 404, json: { detail: "not found" } });
      return;
    }
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { order_id: "ord-1", recommendation_id: "rec-phase1-e2e", replay_run_id: 22, symbol: "AAPL", side: "buy", shares: 10, limit_price: 121, status: "filled", market_data_source: "polygon", fallback_mode: false } });
      return;
    }
    await route.fulfill({ json: { items: [{ order_id: "ord-1", replay_run_id: 22, recommendation_id: "rec-phase1-e2e", symbol: "AAPL", status: "filled", side: "buy", shares: 10, limit_price: 121, created_at: "2026-04-04", market_data_source: "polygon", fallback_mode: false, fills: [{ fill_price: 121, filled_shares: 10, timestamp: "2026-04-04T00:00:01Z" }] }] } });
  });

  await page.goto("/analysis");
  await page.getByTestId("analysis-refresh-button").click();
  await page.getByTestId("analysis-create-recommendation-button").click();

  // URL includes other query params before recommendation= depending on guided state
  await expect(page).toHaveURL(/\/recommendations.*recommendation=rec-phase1-e2e/);
  // Wait for the recommendation to load and auto-select from URL params before navigating
  await expect(page.getByRole("button", { name: "Go to Replay step" })).toBeEnabled();
  await page.getByRole("button", { name: "Go to Replay step" }).click();
  await expect(page).toHaveURL(/\/replay-runs.*recommendation=rec-phase1-e2e/);
  await page.getByRole("button", { name: "Run replay now" }).click();
  await expect(page.getByText("replay complete")).toBeVisible();
  await expect(page.getByText("Replay completed, but no fills occurred. Portfolio remained unchanged.")).toBeVisible();
  // Workflow lineage card always visible — Phase 6 follow-up replaced raw "recommendation: rec_xxx"
  // with the operator-readable breadcrumb produced by formatLineageBreadcrumb. The promoted
  // recommendation_id "rec-phase1-e2e" shortens to "Rec #e1-e2e" (last 6 chars of the hex tail).
  await expect(page.getByText(/Rec #e1-e2e/).first()).toBeVisible();
  await expect(page.getByText(/Replay #22/).first()).toBeVisible();

  await page.getByRole("button", { name: "Go to Paper Order step" }).click();
  await expect(page).toHaveURL(/\/orders\?.*recommendation=rec-phase1-e2e.*replay_run=22/);
  await page.getByRole("button", { name: "Stage paper order now" }).click();
  await expect(page.getByText("Order id:")).toBeVisible();
  await expect(page.getByText("ord-1", { exact: true })).toBeVisible();
});

test("dashboard and provider-health show matching provider truth chips/messages in healthy provider mode", async ({ page }) => {
  await page.route("**/api/user/dashboard", async (route) => {
    await route.fulfill({
      json: {
        market_regime: "risk_on",
        last_refresh: "2026-04-04T00:00:00Z",
        account: { app_role: "admin", approval_status: "approved" },
        provider_health: {
          summary: "ok",
          auth: "ok",
          email: "ok",
          market_data: "polygon",
          configured_provider: "polygon",
          effective_read_mode: "provider",
          workflow_execution_mode: "provider",
          failure_reason: null,
        },
        active_recommendations: [],
        recent_replay_runs: [],
        recent_orders: [],
        pending_admin_actions: [],
        alerts: [],
        workflow_guide: ["check provider truth"],
      },
    });
  });
  await page.route("**/api/admin/provider-health", async (route) => {
    await route.fulfill({
      json: {
        checked_at: "2026-04-04T00:00:00Z",
        providers: [
          { provider: "market_data", mode: "configured", status: "ok", details: "polygon healthy", configured_provider: "polygon", effective_read_mode: "provider", workflow_execution_mode: "provider", operational_impact: "workflows on provider-backed bars", failure_reason: null },
        ],
      },
    });
  });

  await page.goto("/dashboard");
  // Use exact match to target the workflow_execution_mode badge specifically
  await expect(page.getByText("provider", { exact: true })).toBeVisible();
  await expect(page.getByText(/configured: polygon · reads: provider/i)).toBeVisible();

  await page.goto("/admin/provider-health");
  await expect(page.getByText(/workflow mode: provider/i)).toBeVisible();
  // Provider-health renders "configured: <provider>" and "reads: <mode>" as separate elements
  await expect(page.getByText(/configured:.*polygon/i)).toBeVisible();
  await expect(page.getByText(/reads:.*provider/i)).toBeVisible();
  await expect(page.getByText(/provider-backed bars/i)).toBeVisible();
});

test("dashboard and provider-health show matching provider truth chips/messages in demo fallback mode", async ({ page }) => {
  await page.route("**/api/user/dashboard", async (route) => {
    await route.fulfill({
      json: {
        market_regime: "risk_on",
        last_refresh: "2026-04-04T00:00:00Z",
        account: { app_role: "admin", approval_status: "approved" },
        provider_health: {
          summary: "degraded",
          auth: "ok",
          email: "ok",
          market_data: "degraded",
          configured_provider: "polygon",
          effective_read_mode: "fallback",
          workflow_execution_mode: "demo_fallback",
          failure_reason: "quota",
        },
        active_recommendations: [],
        recent_replay_runs: [],
        recent_orders: [],
        pending_admin_actions: [],
        alerts: [],
        workflow_guide: ["check provider truth"],
      },
    });
  });
  await page.route("**/api/admin/provider-health", async (route) => {
    await route.fulfill({
      json: {
        checked_at: "2026-04-04T00:00:00Z",
        providers: [
          { provider: "market_data", mode: "configured", status: "degraded", details: "quota", configured_provider: "polygon", effective_read_mode: "fallback", workflow_execution_mode: "demo_fallback", operational_impact: "workflows on explicit deterministic demo fallback bars", failure_reason: "quota" },
        ],
      },
    });
  });

  await page.goto("/dashboard");
  await expect(page.getByText("demo_fallback")).toBeVisible();
  await expect(page.getByText(/configured: polygon · reads: fallback/i)).toBeVisible();

  await page.goto("/admin/provider-health");
  await expect(page.getByText(/workflow mode: demo_fallback/i)).toBeVisible();
  // Provider-health renders "configured: <provider>" and "reads: <mode>" as separate elements
  await expect(page.getByText(/configured:.*polygon/i)).toBeVisible();
  await expect(page.getByText(/reads:.*fallback/i)).toBeVisible();
  // Use the specific "workflows on" paragraph to avoid matching the longer summary paragraph
  await expect(page.getByText(/workflows on.*deterministic demo fallback bars/i)).toBeVisible();
});
