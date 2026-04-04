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

test("analysis -> recommendations -> replay -> orders click path with stale-banner recovery", async ({ page }) => {
  let recommendationListCalls = 0;

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
  await page.route("**/api/user/recommendations/generate", async (route) => {
    await route.fulfill({ json: { recommendation_id: "rec-phase1-e2e", market_data_source: "polygon", fallback_mode: false } });
  });
  await page.route("**/api/user/recommendations**", async (route) => {
    recommendationListCalls += 1;
    if (recommendationListCalls === 1) {
      await route.fulfill({ status: 401, json: { detail: "Invalid token" } });
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
      await route.fulfill({ json: { id: 22, market_data_source: "polygon", fallback_mode: false } });
      return;
    }
    await route.fulfill({ json: { items: [{ id: 22, symbol: "AAPL", created_at: "2026-04-04", recommendation_count: 1, approved_count: 1, fill_count: 1, ending_heat: 0.2, ending_open_notional: 1000, market_data_source: "polygon", fallback_mode: false }] } });
  });
  await page.route("**/api/user/replay-runs/22/steps", async (route) => {
    await route.fulfill({ json: { items: [{ id: 1, step_index: 1, recommendation_id: "rec-phase1-e2e", approved: true, pre_step_snapshot: { current_heat: 0, open_positions_notional: 0, equity: 10000 }, post_step_snapshot: { current_heat: 0.2, open_positions_notional: 1000, equity: 10050 } }] } });
  });
  await page.route("**/api/user/orders", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { order_id: "ord-1", market_data_source: "polygon", fallback_mode: false } });
      return;
    }
    await route.fulfill({ json: { items: [{ order_id: "ord-1", recommendation_id: "rec-phase1-e2e", symbol: "AAPL", status: "filled", side: "buy", shares: 10, limit_price: 121, created_at: "2026-04-04", market_data_source: "polygon", fallback_mode: false, fills: [{ fill_price: 121, filled_shares: 10, timestamp: "2026-04-04T00:00:01Z" }] }] } });
  });

  await page.goto("/analysis");
  await page.getByTestId("analysis-refresh-button").click();
  await page.getByTestId("analysis-create-recommendation-button").click();

  await expect(page).toHaveURL(/\/recommendations\?recommendation=rec-phase1-e2e/);
  await expect(page.getByText("Recommendations unavailable")).toBeVisible();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByText("Recommendations unavailable")).toHaveCount(0);

  await page.getByRole("button", { name: "Run replay with context" }).click();
  await expect(page).toHaveURL(/\/replay-runs\?symbol=AAPL&recommendation=rec-phase1-e2e/);
  await page.getByRole("button", { name: "Run replay" }).click();
  await expect(page.getByText("replay complete")).toBeVisible();

  await page.goto("/recommendations?recommendation=rec-phase1-e2e");
  await page.getByRole("button", { name: "Stage paper order" }).click();
  await expect(page).toHaveURL(/\/orders\?recommendation=rec-phase1-e2e/);
  await page.getByRole("button", { name: "Stage paper order" }).click();
  await expect(page.getByText("Order id:")).toBeVisible();
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
  await expect(page.getByText("provider")).toBeVisible();
  await expect(page.getByText(/configured: polygon · reads: provider/i)).toBeVisible();

  await page.goto("/admin/provider-health");
  await expect(page.getByText(/workflow mode: provider/i)).toBeVisible();
  await expect(page.getByText(/configured provider: polygon/i)).toBeVisible();
  await expect(page.getByText(/effective read mode: provider/i)).toBeVisible();
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
  await expect(page.getByText(/configured provider: polygon/i)).toBeVisible();
  await expect(page.getByText(/effective read mode: fallback/i)).toBeVisible();
  await expect(page.getByText(/deterministic demo fallback bars/i)).toBeVisible();
});
