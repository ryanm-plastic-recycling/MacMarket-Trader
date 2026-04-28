import { expect, test } from "@playwright/test";

// Pass 4 lifecycle additions to /orders:
//   1. Cancel button visible when an order is staged with no fills.
//   2. Cancel button NOT visible when the order has fills.
//   3. Reopen button visible on a closed trade when closed_at < 5 min ago.
//   4. Reopen button NOT visible when closed_at > 5 min ago.

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not mocked in e2e" } });
  });
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({ json: { app_role: null, approval_status: "approved" } });
  });
  await page.route("**/api/user/orders/portfolio-summary", async (route) =>
    route.fulfill({ status: 404, json: { detail: "not found" } }),
  );
  await page.route("**/api/user/paper-positions**", async (route) => route.fulfill({ json: [] }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [] }));
});

function stagedOrder(opts: { order_id: string }) {
  return {
    order_id: opts.order_id,
    recommendation_id: "rec-staged",
    replay_run_id: null,
    symbol: "AAPL",
    status: "staged",
    side: "buy",
    shares: 10,
    limit_price: 121,
    created_at: "2026-04-28T09:30:00Z",
    canceled_at: null,
    market_data_source: "polygon",
    fallback_mode: false,
    fills: [],
  };
}

function filledOrder(opts: { order_id: string }) {
  return {
    order_id: opts.order_id,
    recommendation_id: "rec-filled",
    replay_run_id: 22,
    symbol: "AAPL",
    status: "filled",
    side: "buy",
    shares: 10,
    limit_price: 121,
    created_at: "2026-04-28T09:30:00Z",
    canceled_at: null,
    market_data_source: "polygon",
    fallback_mode: false,
    fills: [{ fill_price: 121, filled_shares: 10, timestamp: "2026-04-28T09:31:00Z" }],
  };
}

function closedTrade(opts: { id: number; closed_at: string; symbol?: string; realized_pnl?: number; position_id?: number }) {
  return {
    id: opts.id,
    symbol: opts.symbol ?? "AAPL",
    side: "long",
    qty: 10,
    entry_price: 121.0,
    exit_price: 130.0,
    realized_pnl: opts.realized_pnl ?? 90.0,
    opened_at: "2026-04-28T09:31:00Z",
    closed_at: opts.closed_at,
    hold_seconds: 1800,
    position_id: opts.position_id ?? 1,
    recommendation_id: "rec-closed",
    replay_run_id: 22,
    order_id: "ord-closed",
    close_reason: "Target hit",
  };
}

// ---------------------------------------------------------------------------
// Test 1 — Cancel button visible when order is staged with no fills
// ---------------------------------------------------------------------------
test("cancel button is visible when an order is staged with no fills", async ({ page }) => {
  const order = stagedOrder({ order_id: "ord-staged-A" });
  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [order] } }));

  await page.goto("/orders");

  const historyCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Order history" }) });
  await expect(historyCard).toBeVisible();
  await expect(historyCard.getByRole("button", { name: "Cancel order" })).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 2 — Cancel button NOT visible when order has fills
// ---------------------------------------------------------------------------
test("cancel button is NOT visible when an order has fills", async ({ page }) => {
  const order = filledOrder({ order_id: "ord-filled-A" });
  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [order] } }));

  await page.goto("/orders");

  const historyCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Order history" }) });
  await expect(historyCard).toBeVisible();
  // Row renders (so this is not a "card hidden" false positive)
  await expect(historyCard.getByRole("cell", { name: "AAPL" })).toBeVisible();
  await expect(historyCard.getByRole("button", { name: "Cancel order" })).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// Test 3 — Reopen button visible when closed_at < 5 min ago
// ---------------------------------------------------------------------------
test("reopen button is visible on a closed trade when closed_at is within 5 minutes", async ({ page }) => {
  // Use a closed_at 60 seconds ago. Without mocking Date.now we rely on the
  // fact that test execution will see "now" as much later than the closed_at
  // string parsed below — so we generate the timestamp dynamically.
  const closedAt = new Date(Date.now() - 60 * 1000).toISOString();
  const trade = closedTrade({ id: 1, closed_at: closedAt });
  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [trade] }));

  await page.goto("/orders");

  const closedCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Closed trades (last 50)" }) });
  await expect(closedCard).toBeVisible();
  await expect(closedCard.getByRole("button", { name: "Reopen position" })).toBeVisible();
  // Countdown text near the button
  await expect(closedCard.getByText(/\(undo within \d+s\)/)).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 4 — Reopen button NOT visible when closed_at > 5 min ago
// ---------------------------------------------------------------------------
test("reopen button is NOT visible when closed_at is more than 5 minutes ago", async ({ page }) => {
  // closed_at 10 minutes ago — well outside the 5-minute window.
  const closedAt = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  const trade = closedTrade({ id: 2, closed_at: closedAt });
  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [trade] }));

  await page.goto("/orders");

  const closedCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Closed trades (last 50)" }) });
  await expect(closedCard).toBeVisible();
  // Trade row still renders
  await expect(closedCard.getByRole("cell", { name: "AAPL" })).toBeVisible();
  // No reopen button
  await expect(closedCard.getByRole("button", { name: "Reopen position" })).toHaveCount(0);
  // No countdown text either
  await expect(closedCard.getByText(/\(undo within /)).toHaveCount(0);
});
