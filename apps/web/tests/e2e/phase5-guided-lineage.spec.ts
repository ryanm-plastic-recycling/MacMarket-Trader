import { expect, test } from "@playwright/test";

// Phase 5 polish e2e coverage:
//   Test 1 — Guided /analysis hero: WorkflowBanner + step states + TopbarContext guided hint
//   Test 2 — /recommendations guided empty state + queue collapse/toggle
//   Test 3 — /recommendations guided no silent rows[0] fallback (regression for Fix 2, 2026-04-28)
//   Test 4 — /replay-runs guided empty state hero with lineage symbol (no AAPL fallback)
//   Test 5 — /replay-runs zero-fill messaging + equity curve suppression
//   Test 6 — /replay-runs stageability gating with op-error block + reason
//   Test 7 — /orders guided empty state hero + threaded lineage IDs
//   Test 8 — TopbarContext URL-driven regression (guards Fix 1, 2026-04-28)

function chartPayload() {
  // Generate 40 strictly ascending unique dates so the lightweight-charts asc-ordered
  // assertion holds; modulo-based day numbers wrap and break ordering.
  const candles = Array.from({ length: 40 }, (_, idx) => {
    const dayNum = idx + 1;
    const month = dayNum > 31 ? "02" : "01";
    const day = dayNum > 31 ? dayNum - 31 : dayNum;
    return {
      time: `2026-${month}-${String(day).padStart(2, "0")}`,
      open: 100 + idx,
      high: 101 + idx,
      low: 99 + idx,
      close: 100.5 + idx,
      volume: 1_000_000 + idx * 1_000,
    };
  });
  return { symbol: "AAPL", timeframe: "1D", data_source: "polygon", fallback_mode: false, candles, heikin_ashi_candles: candles };
}

// Catch-all 404 for any /api/** request not explicitly mocked, preventing the Next.js dev
// server from proxying to the (absent) Python backend during e2e. Test-level mocks register
// later and override per-endpoint.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not mocked in e2e" } });
  });
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({ json: { app_role: null, approval_status: "approved" } });
  });
});

// ---------------------------------------------------------------------------
// Test 1 — Guided /analysis: banner + step states + topbar guided hint
// ---------------------------------------------------------------------------
test("guided /analysis renders banner step states, topbar guided hint, and Refresh analysis CTA", async ({ page }) => {
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
        active_reason: "phase5 e2e",
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

  // WorkflowBanner renders with proper step states
  await expect(page.getByTestId("workflow-banner")).toBeVisible();
  await expect(page.getByTestId("workflow-step-analyze")).toHaveClass(/is-current/);
  await expect(page.getByTestId("workflow-step-recommendation")).toHaveClass(/is-pending/);
  await expect(page.getByTestId("workflow-step-replay")).toHaveClass(/is-pending/);
  await expect(page.getByTestId("workflow-step-paper-order")).toHaveClass(/is-pending/);

  // TopbarContext shows the guided-no-symbol hint when no symbol is in the URL
  await expect(page.getByText("Guided workflow — start at Analyze")).toBeVisible();

  // Refresh analysis CTA exists and is enabled
  await expect(page.getByTestId("analysis-refresh-button")).toBeVisible();
  await expect(page.getByTestId("analysis-refresh-button")).toBeEnabled();

  // Click refresh (default symbol AAPL, default strategy Event Continuation)
  await page.getByTestId("analysis-refresh-button").click();

  // After applied state propagates, WorkflowBanner chip reflects the applied symbol/strategy.
  // Note: TopbarContext is URL-driven (verified separately in Test 8); refreshAnalysis updates
  // page state without pushing to URL, so the banner chip is the canonical post-refresh signal.
  await expect(page.getByTestId("workflow-banner").getByText(/AAPL · Event Continuation/)).toBeVisible();
});

test("guided /analysis topbar reflects applied symbol/strategy after Refresh analysis pushes URL", async ({ page }) => {
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
        active_reason: "phase5 url-push",
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

  // Pre-refresh: TopbarContext shows the no-symbol guided hint
  await expect(page.getByText("Guided workflow — start at Analyze")).toBeVisible();

  // Wait for initial-load runAnalysis to finish (Clerk auth must settle before refresh click,
  // otherwise refreshAnalysis sees authReady=false and returns null without pushing URL).
  // The setup mock's distinctive active_reason proves the setup payload hydrated.
  await expect(page.getByText("phase5 url-push")).toBeVisible();

  // Click Refresh — refreshAnalysis pushes applied state into the URL via router.replace
  await page.getByTestId("analysis-refresh-button").click();

  // Post-refresh: URL now carries symbol+strategy; TopbarContext reflects "AAPL · Event Continuation"
  await expect(page).toHaveURL(/\/analysis\?.*symbol=AAPL/);
  await expect(page).toHaveURL(/strategy=Event\+Continuation/);
  await expect(page).toHaveURL(/guided=1/);
  await expect(page.getByText("AAPL · Event Continuation").first()).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 2 — /recommendations guided empty state + queue collapse/expand
// ---------------------------------------------------------------------------
test("guided /recommendations renders no-active-rec empty state and collapsed-queue toggle", async ({ page }) => {
  await page.route("**/api/user/recommendations**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
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
            thesis: "Continuation thesis",
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
    // GET stored recommendations
    await route.fulfill({ json: { items: [] } });
  });

  await page.goto("/recommendations?guided=1");

  // "Active recommendation" card present, with empty-state hint copy (no rec selected)
  await expect(page.getByText("No active recommendation")).toBeVisible();
  await expect(page.getByText("Create from Analysis or promote one queue candidate to start guided replay.")).toBeVisible();

  // Toggle button is visible with queue count; queue table is collapsed
  await expect(page.getByRole("button", { name: /View recommendation queue \(\d+\)/ })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "rank", exact: true })).not.toBeAttached();

  // Click toggle — queue table now visible, queue row data renders
  await page.getByRole("button", { name: /View recommendation queue/ }).click();
  await expect(page.getByRole("columnheader", { name: "rank", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "AAPL" }).first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "Event Continuation" }).first()).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 3 — Regression for Fix 2 (2026-04-28): no silent rows[0] fallback in guided
// ---------------------------------------------------------------------------
test("guided /recommendations: no silent rows[0] fallback when recommendation id has no match", async ({ page }) => {
  // Stored recommendations exist, but none match the guided recommendation id.
  await page.route("**/api/user/recommendations**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (url.includes("/queue") && method === "POST") {
      await route.fulfill({ json: { queue: [], summary: { total: 0, top_candidate_count: 0, watchlist_count: 0, no_trade_count: 0 } } });
      return;
    }
    await route.fulfill({
      json: {
        items: [{
          id: 1,
          recommendation_id: "rec-other-msft",
          symbol: "MSFT",
          created_at: "2026-04-15T00:00:00Z",
          market_data_source: "polygon",
          fallback_mode: false,
          payload: {
            thesis: "Different rec — should not be picked as fallback",
            workflow: { source_strategy: "Event Continuation" },
          },
        }],
      },
    });
  });

  await page.goto("/recommendations?guided=1&recommendation=rec-missing");

  // Empty-state hint copy must be visible — proves activeRecommendation === null
  await expect(page.getByText("No active recommendation")).toBeVisible();
  await expect(page.getByText("Create from Analysis or promote one queue candidate to start guided replay.")).toBeVisible();

  // Active recommendation card must NOT contain the unrelated rows[0] recommendation id.
  // (rec-other-msft will appear in the persisted-recommendations table, but never inside the
  // Active recommendation card if Fix 2 holds. Scope to the card by heading.)
  const activeCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Active recommendation" }) });
  await expect(activeCard).toBeVisible();
  await expect(activeCard.getByText("rec-other-msft")).toHaveCount(0);
  await expect(activeCard.getByText(/symbol:\s*MSFT/)).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// Test 4 — /replay-runs guided empty-state hero + lineage symbol (no fallback default)
// ---------------------------------------------------------------------------
test("guided /replay-runs empty state shows lineage symbol from active recommendation, not default AAPL", async ({ page }) => {
  const recId = "rec-nvda-lineage";

  await page.route("**/api/user/recommendations**", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 1,
          recommendation_id: recId,
          symbol: "NVDA",
          created_at: "2026-04-15T00:00:00Z",
          market_data_source: "polygon",
          fallback_mode: false,
          payload: {
            thesis: "NVDA earnings continuation",
            entry: { zone_low: 480, zone_high: 485 },
            invalidation: { price: 472, reason: "breakdown" },
            targets: { target_1: 500, target_2: 510 },
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

  // Note: navigate without symbol in URL — hero must derive symbol from the recommendation lineage.
  await page.goto(`/replay-runs?guided=1&recommendation=${recId}`);

  // Guided empty-state hero renders
  await expect(page.getByText("No replay run yet for this recommendation")).toBeVisible();

  // Symbol comes from active recommendation lineage (NVDA) — NOT a static AAPL fallback.
  // Scope to the empty-state card to avoid matching unrelated text.
  const heroCard = page.locator("div.op-card").filter({ hasText: "No replay run yet for this recommendation" });
  await expect(heroCard.getByText(/symbol:.*NVDA/)).toBeVisible();
  await expect(heroCard.getByText(/symbol:.*AAPL/)).toHaveCount(0);

  // Recommendation id from lineage is shown
  await expect(heroCard.getByText(recId)).toBeVisible();

  // Run replay now CTA is present and enabled
  await expect(heroCard.getByRole("button", { name: "Run replay now" })).toBeVisible();
  await expect(heroCard.getByRole("button", { name: "Run replay now" })).toBeEnabled();
});

// ---------------------------------------------------------------------------
// Test 5 — /replay-runs zero-fill messaging + equity curve suppression
// ---------------------------------------------------------------------------
test("replay zero-fill renders no-fills message and suppresses equity curve when equity is flat", async ({ page }) => {
  const recId = "rec-zero-fill-phase5";

  await page.route("**/api/user/recommendations**", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });

  await page.route("**/api/user/replay-runs", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 77,
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

  await page.route("**/api/user/replay-runs/77", async (route) => {
    await route.fulfill({
      json: {
        id: 77,
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

  await page.route("**/api/user/replay-runs/77/steps", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 1,
          step_index: 1,
          recommendation_id: recId,
          approved: false,
          rejection_reason: "risk gate",
          // equity flat across pre/post — distinct count = 1, so equity SVG is suppressed.
          pre_step_snapshot: { equity: 10000, current_heat: 0, open_positions_notional: 0 },
          post_step_snapshot: { equity: 10000, current_heat: 0, open_positions_notional: 0 },
        }],
      },
    });
  });

  await page.goto(`/replay-runs?guided=1&symbol=AAPL&recommendation=${recId}&replay_run=77`);

  // Zero-fill copy renders
  await expect(page.getByText("Replay completed, but no fills occurred. Portfolio remained unchanged.")).toBeVisible();

  // Equity curve label is NOT in the DOM (svg suppressed because <2 distinct equity values)
  await expect(page.getByText("Equity curve (post-step)")).not.toBeAttached();
});

// ---------------------------------------------------------------------------
// Test 6 — /replay-runs stageability gating: op-error block + stageable_reason
// ---------------------------------------------------------------------------
test("replay run with has_stageable_candidate=false renders op-error block and reason", async ({ page }) => {
  const recId = "rec-no-stage-phase5";
  const stageableReason = "No fills occurred during replay; risk gate blocked all approvals.";

  await page.route("**/api/user/recommendations**", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });

  await page.route("**/api/user/replay-runs", async (route) => {
    await route.fulfill({
      json: {
        items: [{
          id: 55,
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
          has_stageable_candidate: false,
          stageable_reason: stageableReason,
        }],
      },
    });
  });

  await page.route("**/api/user/replay-runs/55", async (route) => {
    await route.fulfill({
      json: {
        id: 55,
        symbol: "AAPL",
        source_recommendation_id: recId,
        source_strategy: "Event Continuation",
        market_data_source: "polygon",
        fallback_mode: false,
        has_stageable_candidate: false,
        stageable_reason: stageableReason,
        summary_metrics: { recommendation_count: 1, approved_count: 0, fill_count: 0, ending_heat: 0, ending_open_notional: 0 },
      },
    });
  });

  await page.route("**/api/user/replay-runs/55/steps", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });

  await page.goto(`/replay-runs?guided=1&symbol=AAPL&recommendation=${recId}&replay_run=55`);

  // op-error block shows the canonical heading
  await expect(page.getByText("Replay produced no stageable candidate")).toBeVisible();

  // Stageable reason text is rendered inside the same block
  await expect(page.getByText(stageableReason)).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 7 — /orders guided empty state + threaded lineage IDs
// ---------------------------------------------------------------------------
test("guided /orders empty state renders hero with Stage CTA and threaded lineage IDs", async ({ page }) => {
  const recId = "rec-lineage-orders";
  const replayRunId = "10";

  await page.route("**/api/user/orders**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: { order_id: "ord-x", recommendation_id: recId, replay_run_id: Number(replayRunId), symbol: "AAPL", side: "buy", shares: 10, limit_price: 121, status: "filled", market_data_source: "polygon", fallback_mode: false } });
      return;
    }
    await route.fulfill({ json: { items: [] } });
  });

  await page.route(`**/api/user/replay-runs/${replayRunId}`, async (route) => {
    await route.fulfill({
      json: {
        id: Number(replayRunId),
        symbol: "AAPL",
        source_recommendation_id: recId,
        source_strategy: "Event Continuation",
        market_data_source: "polygon",
        fallback_mode: false,
        has_stageable_candidate: true,
        summary_metrics: { recommendation_count: 1, approved_count: 1, fill_count: 1, ending_heat: 0, ending_open_notional: 1210 },
      },
    });
  });

  await page.route("**/api/user/orders/portfolio-summary", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not found" } });
  });

  await page.goto(`/orders?guided=1&recommendation=${recId}&replay_run=${replayRunId}&symbol=AAPL&strategy=Event+Continuation`);

  // Guided empty-state hero
  await expect(page.getByText("No paper order staged yet")).toBeVisible();

  // Stage paper order CTA — first occurrence is the in-hero button
  await expect(page.getByRole("button", { name: "Stage paper order now" }).first()).toBeVisible();

  // Workflow lineage block shows the threaded IDs (recommendation → replay → order placeholder)
  const lineageCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Workflow lineage" }) });
  await expect(lineageCard).toBeVisible();
  await expect(lineageCard.getByText(recId)).toBeVisible();
  await expect(lineageCard.getByText(new RegExp(`replay run:\\s*${replayRunId}`))).toBeVisible();
  await expect(lineageCard.getByText(/paper order:\s*—/)).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 8 — TopbarContext URL-driven regression (guards Fix 1, 2026-04-28)
// ---------------------------------------------------------------------------
test("topbar context renders explorer / guided-start / lineage text from URL params", async ({ page }) => {
  // Minimal mocks so /analysis renders without crashing — topbar is independent of page errors,
  // but the page must not unmount the layout before the assertion runs.
  await page.route("**/api/user/strategy-registry", async (route) => {
    await route.fulfill({ json: [{ strategy_id: "event_continuation", display_name: "Event Continuation", market_modes: ["equities"] }] });
  });
  await page.route("**/api/user/analysis/setup**", async (route) => {
    await route.fulfill({ status: 503, json: { detail: "ignored in topbar test" } });
  });

  // Phase A — no guided param: TopbarContext renders "Explorer mode"
  await page.goto("/analysis");
  await expect(page.getByText("Explorer mode")).toBeVisible();

  // Phase B — guided=1, no symbol: shows the guided-start hint
  await page.goto("/analysis?guided=1");
  await expect(page.getByText("Guided workflow — start at Analyze")).toBeVisible();

  // Phase C — guided=1 with symbol + strategy: shows "{SYMBOL} · {strategy}"
  await page.goto("/analysis?guided=1&symbol=NVDA&strategy=Event%20Continuation");
  await expect(page.getByText("NVDA · Event Continuation")).toBeVisible();
});
