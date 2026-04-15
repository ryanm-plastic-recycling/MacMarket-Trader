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
// Without this, any unmocked API call hits the real Next.js route which tries to reach the
// Python backend, causes ECONNRESET, and can crash concurrent test navigations with ERR_ABORTED.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not mocked in e2e" } });
  });
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({ json: { app_role: null, approval_status: "approved" } });
  });
});

// ---------------------------------------------------------------------------
// Test 1 — Guided /analysis: WorkflowBanner step states + TopbarContext hint
// ---------------------------------------------------------------------------
test("guided /analysis renders WorkflowBanner step states and TopbarContext guided hint", async ({ page }) => {
  await page.route("**/api/user/strategy-registry", async (route) => {
    await route.fulfill({ json: [{ strategy_id: "event_continuation", display_name: "Event Continuation", market_modes: ["equities"] }] });
  });
  await page.route("**/api/user/analysis/setup**", async (route) => {
    await route.fulfill({
      json: {
        market_mode: "equities",
        workflow_source: "polygon",
        strategy: "Event Continuation",
        active: true,
        active_reason: "e2e",
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

  await page.goto("/analysis?guided=1");

  // WorkflowBanner renders and Analyze step is current
  await expect(page.getByTestId("workflow-banner")).toBeVisible();
  await expect(page.getByTestId("workflow-step-analyze")).toHaveClass(/is-current/);
  await expect(page.getByTestId("workflow-step-recommendation")).toHaveClass(/is-pending/);
  await expect(page.getByTestId("workflow-step-replay")).toHaveClass(/is-pending/);
  await expect(page.getByTestId("workflow-step-paper-order")).toHaveClass(/is-pending/);

  // TopbarContext shows guided hint when no symbol is in the URL query string
  await expect(page.getByText("Guided workflow — start at Analyze")).toBeVisible();

  // Click refresh to load setup (ensures chart ref is ready)
  await page.getByTestId("analysis-refresh-button").click();

  // Create-recommendation CTA appears after setup loads
  await expect(page.getByTestId("analysis-create-recommendation-button")).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 2 — Recommendations guided: queue collapsed by default, toggle expands
// ---------------------------------------------------------------------------
test("recommendations guided mode — queue collapsed by default, toggle expands table", async ({ page }) => {
  await page.route("**/api/user/recommendations**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (url.includes("/queue/promote")) {
      await route.fulfill({ json: { recommendation_id: "rec-e2e", action: "make_active", approved: true } });
      return;
    }
    if (url.includes("/queue") && method === "POST") {
      await route.fulfill({
        json: {
          queue: [{
            rank: 1,
            symbol: "AAPL",
            strategy: "Event Continuation",
            timeframe: "1D",
            market_mode: "equities",
            workflow_source: "polygon",
            status: "top_candidate",
            score: 0.82,
            expected_rr: 1.8,
            confidence: 0.66,
            thesis: "Post-earnings continuation",
            trigger: "hold above prior-day high",
            entry_zone: { low: 120, high: 122 },
            invalidation: { price: 118, reason: "breakdown" },
            targets: [126, 129],
            reason_text: "Strong regime alignment",
          }],
          summary: { total: 1, top_candidate_count: 1, watchlist_count: 0, no_trade_count: 0 },
        },
      });
      return;
    }
    // GET recommendations list
    await route.fulfill({ json: { items: [] } });
  });

  await page.goto("/recommendations?guided=1");

  // Guided empty-state hero renders when no recommendation is active
  await expect(page.getByText("No active recommendation")).toBeVisible();

  // Toggle button is visible with queue count
  await expect(page.getByRole("button", { name: /View recommendation queue \(\d+\)/ })).toBeVisible();

  // Queue table is collapsed — "rank" column header not in DOM
  await expect(page.getByRole("columnheader", { name: "rank", exact: true })).not.toBeAttached();

  // Click toggle to expand
  await page.getByRole("button", { name: /View recommendation queue/ }).click();

  // Queue table now visible — "rank" column header present
  await expect(page.getByRole("columnheader", { name: "rank", exact: true })).toBeVisible();

  // Queue row data renders
  await expect(page.getByRole("cell", { name: "AAPL" }).first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "Event Continuation" }).first()).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 3 — Replay guided empty state: no run yet, hero + Run replay now CTA
// ---------------------------------------------------------------------------
test("replay guided empty state renders hero with Run replay now CTA when no run exists", async ({ page }) => {
  const recId = "rec-guided-e2e";

  await page.route("**/api/user/recommendations**", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 1,
          recommendation_id: recId,
          symbol: "AAPL",
          created_at: "2026-04-15T00:00:00Z",
          market_data_source: "polygon",
          fallback_mode: false,
          payload: {
            thesis: "Earnings continuation with sector leadership",
            entry: { zone_low: 120, zone_high: 122 },
            invalidation: { price: 118, reason: "breakdown" },
            targets: { target_1: 126, target_2: 129 },
            workflow: { source_strategy: "Event Continuation" },
          },
        }],
      },
    });
  });

  await page.route("**/api/user/replay-runs", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { id: 99, market_data_source: "polygon", fallback_mode: false, summary_metrics: { recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0 } } });
      return;
    }
    await route.fulfill({ json: { items: [] } });
  });

  await page.goto(`/replay-runs?guided=1&symbol=AAPL&strategy=Event+Continuation&recommendation=${recId}`);

  // Guided empty-state hero renders
  await expect(page.getByText("No replay run yet for this recommendation")).toBeVisible();

  // Symbol comes from lineage — not a stale default (first match to avoid strict-mode with duplicate symbol rows)
  await expect(page.getByText(/symbol:.*AAPL/).first()).toBeVisible();

  // Recommendation ID is shown from lineage
  await expect(page.getByText(recId).first()).toBeVisible();

  // Run replay now CTA is present — first occurrence is the hero card button
  await expect(page.getByRole("button", { name: "Run replay now" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Run replay now" }).first()).toBeEnabled();
});

// ---------------------------------------------------------------------------
// Test 4 — Replay zero-fill: message renders, equity curve suppressed
// ---------------------------------------------------------------------------
test("replay zero-fill message renders and equity curve is suppressed", async ({ page }) => {
  const recId = "rec-zero-fill-e2e";

  await page.route("**/api/user/recommendations**", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });

  // Always return the run — navigate directly with replay_run=42 so it is auto-selected
  await page.route("**/api/user/replay-runs", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 42,
          symbol: "AAPL",
          source_recommendation_id: recId,
          created_at: "2026-04-15",
          recommendation_count: 1,
          approved_count: 0,
          fill_count: 0,
          ending_heat: 0,
          ending_open_notional: 0,
          market_data_source: "polygon",
          fallback_mode: false,
        }],
      },
    });
  });

  await page.route("**/api/user/replay-runs/42", async (route) => {
    await route.fulfill({
      json: {
        id: 42,
        symbol: "AAPL",
        source_recommendation_id: recId,
        source_strategy: "Event Continuation",
        market_data_source: "polygon",
        fallback_mode: false,
        summary_metrics: { recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0 },
        thesis: null,
        key_levels: null,
      },
    });
  });

  await page.route("**/api/user/replay-runs/42/steps", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 1,
          step_index: 1,
          recommendation_id: recId,
          approved: false,
          rejection_reason: "risk gate: heat limit",
          pre_step_snapshot: { equity: 10000, current_heat: 0, open_positions_notional: 0 },
          post_step_snapshot: { equity: 10000, current_heat: 0, open_positions_notional: 0 },
        }],
      },
    });
  });

  // Navigate with replay_run=42 so pickReplayRunSelection auto-selects it
  await page.goto(`/replay-runs?guided=1&symbol=AAPL&recommendation=${recId}&replay_run=42`);

  // Zero-fill message renders when selected run has no fills
  await expect(page.getByText("Replay completed, but no fills occurred. Portfolio remained unchanged.")).toBeVisible();

  // Equity curve div is suppressed (equity has no variance — same value across all steps)
  await expect(page.getByText("Equity curve (post-step)")).not.toBeAttached();
});

// ---------------------------------------------------------------------------
// Test 5 — Orders guided empty state + stageability block
// ---------------------------------------------------------------------------
test("orders guided empty state renders hero and stageability block when replay has no candidate", async ({ page }) => {
  await page.route("**/api/user/orders**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { order_id: "ord-1", recommendation_id: "rec-e2e", replay_run_id: 22, symbol: "AAPL", side: "buy", shares: 10, limit_price: 121, status: "filled", market_data_source: "polygon", fallback_mode: false } });
      return;
    }
    await route.fulfill({ json: { items: [] } });
  });

  await page.route("**/api/user/replay-runs/22", async (route) => {
    await route.fulfill({
      json: {
        id: 22,
        symbol: "AAPL",
        source_recommendation_id: "rec-e2e",
        source_strategy: "Event Continuation",
        market_data_source: "polygon",
        fallback_mode: false,
        has_stageable_candidate: false,
        stageable_reason: "No fills occurred during replay.",
        summary_metrics: { recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0 },
      },
    });
  });

  await page.route("**/api/user/orders/portfolio-summary", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not found" } });
  });

  await page.goto("/orders?guided=1&recommendation=rec-e2e&replay_run=22&symbol=AAPL&strategy=Event+Continuation");

  // Guided empty-state hero renders
  await expect(page.getByText("No paper order staged yet")).toBeVisible();

  // Stage paper order CTA is present
  await expect(page.getByRole("button", { name: "Stage paper order now" }).first()).toBeVisible();

  // Stageability block renders when replay has no stageable candidate
  await expect(page.getByText("No paper order can be staged from this replay.")).toBeVisible();
  await expect(page.getByText("No fills occurred during replay.")).toBeVisible();
});
