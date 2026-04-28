import { expect, test } from "@playwright/test";

// Catch-all + /api/user/me mock pattern matches the rest of the e2e suite —
// keeps the dev server from proxying to the (absent) Python backend.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not mocked in e2e" } });
  });
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({ json: { app_role: null, approval_status: "approved" } });
  });
});

// ---------------------------------------------------------------------------
// Phase 6 close-out follow-up — Section 3
// Asserts that clicking "Make active" in the guided Next action card
// auto-advances the operator to /replay-runs within ~1500ms with the
// promoted recommendation_id threaded through the URL.
// ---------------------------------------------------------------------------
test("guided Make active auto-advances to /replay-runs with recommendation_id in URL", async ({ page }) => {
  const promotedRecId = "rec_e2e_advance_abcdef";

  await page.route("**/api/user/recommendations**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (url.includes("/queue/promote")) {
      await route.fulfill({
        json: {
          id: 99,
          recommendation_id: promotedRecId,
          symbol: "AAPL",
          strategy: "Event Continuation",
          action: "make_active",
          market_data_source: "polygon",
          fallback_mode: false,
          ranking_provenance: { strategy: "Event Continuation", rank: 1 },
          approved: true,
        },
      });
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
    // GET stored recommendations — return a list including the promoted one so
    // loadRecommendations() can resolve before the auto-advance fires.
    await route.fulfill({
      json: {
        items: [{
          id: 99,
          recommendation_id: promotedRecId,
          symbol: "AAPL",
          created_at: "2026-04-28T12:00:00Z",
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

  // Replay runs list — empty so the destination page renders cleanly.
  await page.route("**/api/user/replay-runs**", async (route) => {
    await route.fulfill({ json: { items: [] } });
  });

  await page.goto("/recommendations?guided=1&symbol=AAPL");

  // Wait for the queue to load so a candidate is selected and Make active is enabled.
  await expect(page.getByRole("cell", { name: "AAPL" }).first()).toBeVisible();

  // Click the primary CTA in the Next action card.
  await page.getByRole("button", { name: /Make active/ }).first().click();

  // Auto-advance fires after a 600ms delay. Wait up to 1500ms for the URL change.
  await page.waitForURL(/\/replay-runs/, { timeout: 1500 });

  // The promoted recommendation_id must be threaded through the URL.
  expect(page.url()).toContain(`recommendation=${promotedRecId}`);
  expect(page.url()).toContain("guided=1");
});
